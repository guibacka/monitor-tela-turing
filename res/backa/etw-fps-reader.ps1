# Leitor de FPS pelos eventos do Windows (ETW), usado pelo monitor (Backa) quando o PresentMon não consegue rodar
# (ex.: anti-cheat do Battlefield 6 bloqueia criar sessões de captura novas com o jogo aberto).
#
# Conecta nas sessões de tempo real já existentes passadas em -Sessions e conta os eventos "Present" do DirectX
# (DXGI e D3D9) por processo. A contagem é feita em C# (compilado na hora pelo próprio Windows): são dezenas de
# milhares de eventos por segundo, rápido demais para fazer em Python.
#
# Saída (stdout), a cada 0,5 s:  FPS <sessão> <pid>:<fps> <pid>:<fps> ...   (da sessão com quadros mais recentes)
#                                END <sessão> <código>                      (quando a leitura de uma sessão termina)
param([Parameter(Mandatory = $true)][string]$Sessions)  # nomes separados por vírgula

$ErrorActionPreference = "Stop"
Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public class BackaEtwSession
{
    [DllImport("advapi32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern ulong OpenTraceW(IntPtr logfile);
    [DllImport("advapi32.dll")]
    static extern uint ProcessTrace(ulong[] handles, uint count, IntPtr start, IntPtr end);
    [DllImport("advapi32.dll")]
    static extern uint CloseTrace(ulong handle);

    [UnmanagedFunctionPointer(CallingConvention.Winapi)]
    delegate void EventRecordCallback(IntPtr record);

    // GUIDs (16 bytes, como ficam na memória) dos provedores e os IDs dos eventos de início de Present
    static readonly long DxgiA = BitConverter.ToInt64(new Guid("CA11C036-0102-4A2D-A6AD-F03CFED5D3C9").ToByteArray(), 0);
    static readonly long DxgiB = BitConverter.ToInt64(new Guid("CA11C036-0102-4A2D-A6AD-F03CFED5D3C9").ToByteArray(), 8);
    static readonly long D3d9A = BitConverter.ToInt64(new Guid("783ACA0A-790E-4D7F-8451-AA850511C6B9").ToByteArray(), 0);
    static readonly long D3d9B = BitConverter.ToInt64(new Guid("783ACA0A-790E-4D7F-8451-AA850511C6B9").ToByteArray(), 8);
    const double Fresh = 3.0;  // quadros mais velhos que isto (acumulados antes de conectar) não contam

    public readonly string Name;
    public volatile bool Alive;
    public uint Result;
    public long NewestFresh;  // horário (FILETIME) do quadro mais novo recebido na hora
    readonly object sync = new object();
    readonly Dictionary<long, Queue<long>> frames = new Dictionary<long, Queue<long>>();  // (pid, api) -> horários
    EventRecordCallback callback;
    IntPtr logfile, loggerName;
    ulong handle;

    public BackaEtwSession(string name) { Name = name; }

    public bool Start()
    {
        callback = OnEvent;
        logfile = Marshal.AllocHGlobal(448);
        for (int i = 0; i < 448; i += 8) Marshal.WriteInt64(logfile, i, 0);
        loggerName = Marshal.StringToHGlobalUni(Name);
        Marshal.WriteIntPtr(logfile, 8, loggerName);                 // LoggerName
        Marshal.WriteInt32(logfile, 28, 0x100 | 0x10000000);         // tempo real + EVENT_RECORD
        Marshal.WriteIntPtr(logfile, 424, Marshal.GetFunctionPointerForDelegate(callback));
        handle = OpenTraceW(logfile);
        if (handle == ulong.MaxValue) { Result = (uint)Marshal.GetLastWin32Error(); return false; }
        Alive = true;
        Thread t = new Thread(Run);
        t.IsBackground = true;
        t.Start();
        return true;
    }

    void Run()
    {
        Result = ProcessTrace(new ulong[] { handle }, 1, IntPtr.Zero, IntPtr.Zero);
        Alive = false;
    }

    void OnEvent(IntPtr r)
    {
        long a = Marshal.ReadInt64(r, 24), b = Marshal.ReadInt64(r, 32);
        int id = Marshal.ReadInt16(r, 40), api;
        if (a == DxgiA && b == DxgiB && (id == 42 || id == 55)) api = 1;
        else if (a == D3d9A && b == D3d9B && id == 1) api = 2;
        else return;
        long when = Marshal.ReadInt64(r, 16);
        if ((DateTime.UtcNow.ToFileTimeUtc() - when) / 1e7 > Fresh) return;
        long key = (long)(uint)Marshal.ReadInt32(r, 12) * 4 + api;
        lock (sync)
        {
            Queue<long> q;
            if (!frames.TryGetValue(key, out q)) { q = new Queue<long>(); frames[key] = q; }
            q.Enqueue(when);
            while (when - q.Peek() > 20000000) q.Dequeue();
            if (when > NewestFresh) NewestFresh = when;
        }
    }

    // "pid:fps ..." com os quadros do último 1 s (até o quadro mais novo; a entrega tem até ~1 s de atraso).
    // O mesmo quadro pode vir pelo DXGI e pelo D3D9: vale o maior dos dois, não a soma.
    public string Report()
    {
        long now = DateTime.UtcNow.ToFileTimeUtc();
        Dictionary<uint, int> best = new Dictionary<uint, int>();
        lock (sync)
        {
            List<long> old = new List<long>();
            foreach (KeyValuePair<long, Queue<long>> kv in frames)
            {
                Queue<long> q = kv.Value;
                long newest = 0, count = 0;
                foreach (long t in q) newest = t;
                if ((now - newest) / 1e7 > 5) { old.Add(kv.Key); continue; }
                if ((now - newest) / 1e7 > Fresh) continue;
                foreach (long t in q) if (newest - t < 10000000) count++;
                uint pid = (uint)(kv.Key >> 2);
                int prev;
                if (!best.TryGetValue(pid, out prev) || count > prev) best[pid] = (int)count;
            }
            foreach (long k in old) frames.Remove(k);
        }
        StringBuilder sb = new StringBuilder();
        foreach (KeyValuePair<uint, int> kv in best) sb.Append(' ').Append(kv.Key).Append(':').Append(kv.Value);
        return sb.ToString();
    }
}
'@

$readers = @()
foreach ($name in ($Sessions -split ',' | Where-Object { $_.Trim() } | ForEach-Object { $_.Trim() })) {
    $r = New-Object BackaEtwSession $name
    if ($r.Start()) { $readers += $r } else { [Console]::Out.WriteLine("END $name $($r.Result)") }
}
[Console]::Out.Flush()
$ended = @{}
$current = $null
while ($true) {
    Start-Sleep -Milliseconds 500
    $alive = @($readers | Where-Object { $_.Alive })
    foreach ($r in $readers) {
        if (-not $r.Alive -and -not $ended.ContainsKey($r.Name)) {
            $ended[$r.Name] = $true
            [Console]::Out.WriteLine("END $($r.Name) $($r.Result)")
        }
    }
    if ($alive.Count -eq 0) { break }
    # Todas as sessões podem receber os mesmos eventos: usa a que tem o quadro mais recente, mas só troca de
    # sessão se a atual ficar mais de 1 s atrás (senão ficaria alternando entre sessões iguais)
    $best = $alive | Sort-Object -Property NewestFresh -Descending | Select-Object -First 1
    if ($current -and $current.Alive -and ($best.NewestFresh - $current.NewestFresh) -lt 10000000) { $best = $current }
    $current = $best
    [Console]::Out.WriteLine("FPS $($best.Name)$($best.Report())")
    [Console]::Out.Flush()
}
