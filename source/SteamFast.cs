// ============================================================================
//  蒸汽快线 SteamFast v3.0  ——  原生单文件版（.NET Framework 4.8 / C# 5）
//
//  设计要点
//  1) 一个 exe 两种角色：
//       正常双击   → 图形界面（清单是 asInvoker，不弹 UAC）
//       点「一键加速」→ 用 ShellExecute("runas") 再起一个自己，带 --job 参数，
//                      只有这一刻弹一次 UAC；干活的进程不带界面，写完就退。
//  2) 界面做 DPI 等比放大：本机 2560x1600 / 150% 缩放，不做的话会被位图拉伸、字发虚。
//  3) 加速原理：多源 DNS（含系统 DNS 与内置种子 IP）找候选 → TCP 握手测速 →
//     TLS 握手 + 证书域名校验 → 真实 HTTPS 请求校验状态码 →
//     只把"真的能打开"的最快 IP 写进 hosts 的标记区块（插在 Steam++ 条目之前）。
//
//  3b) 能力边界（v3.0 起明确写死，不再假装全能）：
//     hosts 只能修"DNS 给错/给慢 IP"这一类问题。
//     如果某个域名在 IP 层或 TLS(SNI) 层被拦（表现为 TCP 超时 / TLS 被 RST），
//     hosts 无论钉哪个 IP 都没用 —— 这类域名本程序会如实报"需完整反代"，
//     不会硬写一条假条目充数。GitHub 的 raw / Release 下载即属此类。
//
//  编译（本机自带编译器，无需装任何东西）：
//     csc.exe /target:winexe /win32icon:SteamFast.ico /win32manifest:app.manifest
//             /out:SteamFast.exe SteamFast.cs /r:System.dll /r:System.Core.dll
//             /r:System.Drawing.dll /r:System.Windows.Forms.dll
// ============================================================================
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.NetworkInformation;
using System.Net.Security;
using System.Net.Sockets;
using System.Security.Authentication;
using System.Security.Cryptography.X509Certificates;
using System.Text;
using System.Threading;
using System.Windows.Forms;
using System.Reflection;

// ---------------------------------------------------------------- 程序集信息
//  写进 PE 头，文件属性里就能看到版本号、说明、版权
[assembly: AssemblyTitle("蒸汽快线 SteamFast")]
[assembly: AssemblyDescription("Steam / GitHub 网络加速工具（hosts 优选 IP + 真实 HTTPS 校验）")]
[assembly: AssemblyProduct("蒸汽快线 SteamFast")]
[assembly: AssemblyCompany("")]
[assembly: AssemblyCopyright("")]
[assembly: AssemblyVersion("3.0.0.0")]
[assembly: AssemblyFileVersion("3.0.0.0")]
[assembly: AssemblyInformationalVersion("3.0.0")]

namespace SteamFast
{
    // ========================================================================
    //  基础信息
    // ========================================================================
    static class AppInfo
    {
        public const string Title = "蒸汽快线 SteamFast";
        public const string Version = "3.0.0";
        public const string StartMark = "# ===== SteamFast Start =====";
        public const string EndMark = "# ===== SteamFast End =====";
        public const string SppMark = "# Steam++ Start";
        public const string TaskName = "SteamFast AutoAccel";
        public const string SppAppsFolder = @"shell:AppsFolder\4651ED44255E.47979655102CE_k6txddmbb6c52!App";

        public static string Dir { get { return Path.GetDirectoryName(Application.ExecutablePath); } }
        public static string BackupDir { get { return Path.Combine(Dir, "backup"); } }
        public static string LogDir { get { return Path.Combine(Dir, "logs"); } }
        public static string OriginalBackup { get { return Path.Combine(BackupDir, "hosts_original.bak"); } }
        public static string BeforeApplyBackup { get { return Path.Combine(BackupDir, "hosts_before_apply.bak"); } }
        public static string ExePath { get { return Application.ExecutablePath; } }
        public static readonly string HostsPath =
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.System), @"drivers\etc\hosts");
    }

    // ========================================================================
    //  日志（写文件）
    // ========================================================================
    static class Log
    {
        private static readonly object Gate = new object();
        public static void W(string msg)
        {
            string line = "[" + DateTime.Now.ToString("HH:mm:ss") + "] " + msg;
            lock (Gate)
            {
                try
                {
                    if (!Directory.Exists(AppInfo.LogDir)) Directory.CreateDirectory(AppInfo.LogDir);
                    string f = Path.Combine(AppInfo.LogDir, "SteamFast_" + DateTime.Now.ToString("yyyyMMdd") + ".log");
                    File.AppendAllText(f, line + "\r\n", new UTF8Encoding(false));
                }
                catch { }
            }
        }
    }

    // ========================================================================
    //  DNS（原生 UDP，多源并发，绕开被污染的本地解析）
    // ========================================================================
    static class Dns
    {
        public static readonly string[] Servers = new string[]
        {
            "223.5.5.5", "119.29.29.29", "114.114.114.114", "180.76.76.76", "8.8.8.8"
        };

        /// <summary>本机网卡上配置的 DNS（校园网/运营商），走原始 UDP，不受 hosts 影响。</summary>
        public static List<string> SystemServers()
        {
            List<string> list = new List<string>();
            try
            {
                foreach (NetworkInterface ni in NetworkInterface.GetAllNetworkInterfaces())
                {
                    if (ni.OperationalStatus != OperationalStatus.Up) continue;
                    if (ni.NetworkInterfaceType == NetworkInterfaceType.Loopback) continue;
                    foreach (IPAddress a in ni.GetIPProperties().DnsAddresses)
                    {
                        if (a.AddressFamily != AddressFamily.InterNetwork) continue;
                        string s = a.ToString();
                        if (!list.Contains(s)) list.Add(s);
                    }
                }
            }
            catch { }
            return list;
        }

        /// <summary>用系统 DNS 解析（UDP 直查，不读 hosts，避免自己写进去的条目反过来污染候选）。</summary>
        public static List<string> SystemResolve(string domain, int timeoutMs)
        {
            List<string> found = new List<string>();
            object gate = new object();
            List<Thread> threads = new List<Thread>();
            foreach (string s in SystemServers())
            {
                string server = s;
                Thread t = new Thread(delegate()
                {
                    List<string> ips = QueryOne(domain, server, timeoutMs);
                    lock (gate) { foreach (string ip in ips) if (!found.Contains(ip)) found.Add(ip); }
                });
                t.IsBackground = true;
                t.Start();
                threads.Add(t);
            }
            foreach (Thread t in threads) t.Join(timeoutMs + 300);
            return found;
        }

        public static List<string> Resolve(string domain, int timeoutMs)
        {
            List<string> found = new List<string>();
            object gate = new object();
            List<Thread> threads = new List<Thread>();
            foreach (string s in Servers)
            {
                string server = s;
                Thread t = new Thread(delegate()
                {
                    List<string> ips = QueryOne(domain, server, timeoutMs);
                    lock (gate) { foreach (string ip in ips) if (!found.Contains(ip)) found.Add(ip); }
                });
                t.IsBackground = true;
                t.Start();
                threads.Add(t);
            }
            foreach (Thread t in threads) t.Join(timeoutMs + 400);
            return found;
        }

        private static List<string> QueryOne(string domain, string server, int timeoutMs)
        {
            List<string> ips = new List<string>();
            UdpClient udp = null;
            try
            {
                udp = new UdpClient();
                udp.Client.ReceiveTimeout = timeoutMs;
                udp.Client.SendTimeout = timeoutMs;
                udp.Connect(server, 53);
                int id = new Random(Environment.TickCount + server.GetHashCode()).Next(0, 65535);
                byte[] query = BuildQuery(domain, id);
                udp.Send(query, query.Length);
                IPEndPoint remote = new IPEndPoint(IPAddress.Any, 0);
                byte[] resp = udp.Receive(ref remote);
                ips = ParseAnswers(resp);
            }
            catch { }
            finally { if (udp != null) { try { udp.Close(); } catch { } } }
            return ips;
        }

        private static byte[] BuildQuery(string domain, int id)
        {
            MemoryStream ms = new MemoryStream();
            WriteShort(ms, id);
            WriteShort(ms, 0x0100);
            WriteShort(ms, 1);
            WriteShort(ms, 0);
            WriteShort(ms, 0);
            WriteShort(ms, 0);
            foreach (string p in domain.Split('.'))
            {
                byte[] b = Encoding.ASCII.GetBytes(p);
                ms.WriteByte((byte)b.Length);
                ms.Write(b, 0, b.Length);
            }
            ms.WriteByte(0);
            WriteShort(ms, 1);
            WriteShort(ms, 1);
            return ms.ToArray();
        }

        private static void WriteShort(Stream s, int v)
        {
            s.WriteByte((byte)((v >> 8) & 0xFF));
            s.WriteByte((byte)(v & 0xFF));
        }

        private static int ReadShort(byte[] d, int off) { return (d[off] << 8) | d[off + 1]; }

        private static List<string> ParseAnswers(byte[] d)
        {
            List<string> ips = new List<string>();
            if (d == null || d.Length < 12) return ips;
            int qd = ReadShort(d, 4);
            int an = ReadShort(d, 6);
            if (an == 0) return ips;
            int i = 12;
            for (int q = 0; q < qd && i < d.Length; q++) { i = SkipName(d, i); i += 4; }
            for (int a = 0; a < an && i + 10 <= d.Length; a++)
            {
                i = SkipName(d, i);
                if (i + 10 > d.Length) break;
                int type = ReadShort(d, i);
                int rdlen = ReadShort(d, i + 8);
                i += 10;
                if (i + rdlen > d.Length) break;
                if (type == 1 && rdlen == 4)
                    ips.Add(d[i] + "." + d[i + 1] + "." + d[i + 2] + "." + d[i + 3]);
                i += rdlen;
            }
            return ips;
        }

        private static int SkipName(byte[] d, int i)
        {
            while (i < d.Length)
            {
                int len = d[i];
                if ((len & 0xC0) == 0xC0) return i + 2;
                if (len == 0) return i + 1;
                i += len + 1;
            }
            return i;
        }
    }

    // ========================================================================
    //  内置种子 IP（公共 DNS 被污染时的兜底候选）
    //  说明：这些只是"待测候选"，不是"结论"。任何一个都必须通过
    //        TCP + TLS 证书 + 真实 HTTPS 请求三重校验才会被写进 hosts。
    // ========================================================================
    static class Seeds
    {
        private static readonly Dictionary<string, string[]> Map =
            new Dictionary<string, string[]>(StringComparer.OrdinalIgnoreCase)
        {
            { "github.com", new string[] { "20.205.243.166", "20.27.177.113", "4.237.22.38", "140.82.112.3" } },
            { "api.github.com", new string[] { "20.205.243.168", "20.205.243.166" } },
            { "codeload.github.com", new string[] { "20.205.243.165" } },
            { "gist.github.com", new string[] { "20.205.243.166", "140.82.112.3" } },
            { "github.githubassets.com", new string[] { "185.199.108.154", "185.199.109.154", "185.199.110.154", "185.199.111.154", "185.199.110.215" } },
            { "store.steampowered.com", new string[] { "184.31.230.122", "23.200.214.95" } },
            { "api.steampowered.com", new string[] { "184.24.154.132", "23.210.216.138" } },
            { "login.steampowered.com", new string[] { "23.55.143.33", "23.210.216.146" } },
            { "checkout.steampowered.com", new string[] { "104.103.144.236", "23.54.32.239" } },
            { "media.steampowered.com", new string[] { "23.222.27.136", "23.222.27.147", "23.55.179.196" } },
            { "cdn.akamai.steamstatic.com", new string[] { "104.84.150.183", "23.222.27.147" } },
            { "store.akamai.steamstatic.com", new string[] { "23.210.7.167", "23.222.27.147" } },
            { "community.akamai.steamstatic.com", new string[] { "23.210.7.168", "23.222.27.147" } },
            { "avatars.akamai.steamstatic.com", new string[] { "23.210.7.179", "23.222.27.147" } },
            { "steamcdn-a.akamaihd.net", new string[] { "104.84.150.175", "23.210.216.88" } },
            { "steamuserimages-a.akamaihd.net", new string[] { "23.210.7.177", "23.210.216.88" } },
            { "steamcommunity-a.akamaihd.net", new string[] { "23.210.7.179", "23.222.27.147" } },
            { "community.steamstatic.com", new string[] { "199.232.215.52", "23.222.27.147" } },
            { "hf.co", new string[] { "3.210.66.237" } },
            { "cdn-lfs.hf.co", new string[] { "13.226.69.74" } },
            { "cdn-images.hf.co", new string[] { "13.35.190.40" } }
        };

        private static readonly string[] RawGithub = new string[]
        {
            "185.199.108.133", "185.199.109.133", "185.199.110.133", "185.199.111.133"
        };

        public static List<string> For(string domain)
        {
            List<string> r = new List<string>();
            string[] hit;
            if (Map.TryGetValue(domain, out hit))
                r.AddRange(hit);
            if (domain.EndsWith("githubusercontent.com", StringComparison.OrdinalIgnoreCase))
                foreach (string ip in RawGithub) if (!r.Contains(ip)) r.Add(ip);
            return r;
        }
    }

    // ========================================================================
    //  连通性探测：TCP 握手测速 + TLS 证书验证
    // ========================================================================
    static class Probe
    {
        public static void InitTls()
        {
            try { ServicePointManager.SecurityProtocol = SecurityProtocolType.Tls12; } catch { }
        }

        public static int TcpMs(string ip, int port, int timeoutMs)
        {
            Socket sock = null;
            try
            {
                IPAddress addr;
                if (!IPAddress.TryParse(ip, out addr)) return -1;
                sock = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                Stopwatch sw = Stopwatch.StartNew();
                IAsyncResult ar = sock.BeginConnect(new IPEndPoint(addr, port), null, null);
                if (!ar.AsyncWaitHandle.WaitOne(timeoutMs)) return -1;
                sock.EndConnect(ar);
                sw.Stop();
                return (int)sw.ElapsedMilliseconds;
            }
            catch { return -1; }
            finally { if (sock != null) { try { sock.Close(); } catch { } } }
        }

        public static bool TlsCheck(string host, string ip, int timeoutMs, out int ms)
        {
            ms = -1;
            Socket sock = null;
            try
            {
                IPAddress addr;
                if (!IPAddress.TryParse(ip, out addr)) return false;
                sock = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                IAsyncResult ar = sock.BeginConnect(new IPEndPoint(addr, 443), null, null);
                if (!ar.AsyncWaitHandle.WaitOne(timeoutMs)) return false;
                sock.EndConnect(ar);

                bool[] ok = new bool[1];
                Stopwatch sw = Stopwatch.StartNew();
                using (NetworkStream ns = new NetworkStream(sock, true))
                using (SslStream ssl = new SslStream(ns, false,
                    delegate(object s, X509Certificate c, X509Chain ch, SslPolicyErrors e) { return true; }))
                {
                    SslStream cap = ssl;
                    Thread th = new Thread(delegate()
                    {
                        try { cap.AuthenticateAsClient(host, null, SslProtocols.Tls12, false); ok[0] = true; }
                        catch { ok[0] = false; }
                    });
                    th.IsBackground = true;
                    th.Start();
                    if (!th.Join(timeoutMs)) return false;
                    if (!ok[0]) return false;
                    sw.Stop();
                    ms = (int)sw.ElapsedMilliseconds;
                    X509Certificate rc = ssl.RemoteCertificate;
                    if (rc != null)
                    {
                        X509Certificate2 c2 = new X509Certificate2(rc);
                        if (!CertMatches(host, c2)) return false;
                    }
                    return true;
                }
            }
            catch { return false; }
            finally { if (sock != null) { try { sock.Close(); } catch { } } }
        }

        /// <summary>
        /// 终极判据：TCP 通 + TLS 证书对得上 + 真实 HTTPS 请求能拿到状态行。
        /// 只有这一关过了，才认为"这个 IP 对这个域名真的能用"。
        /// 5xx 视为不可用；4xx 是"路径没内容但服务在"，算可用。
        /// </summary>
        public static bool HttpCheck(string host, string ip, int timeoutMs, out int ms, out int status, out int stage)
        {
            ms = -1; status = 0; stage = 0;
            Socket sock = null;
            SslStream ssl = null;
            try
            {
                IPAddress addr;
                if (!IPAddress.TryParse(ip, out addr)) { stage = 1; return false; }
                sock = new Socket(AddressFamily.InterNetwork, SocketType.Stream, ProtocolType.Tcp);
                IAsyncResult ar = sock.BeginConnect(new IPEndPoint(addr, 443), null, null);
                if (!ar.AsyncWaitHandle.WaitOne(timeoutMs)) { stage = 1; return false; }
                sock.EndConnect(ar);
                sock.ReceiveTimeout = timeoutMs;
                sock.SendTimeout = timeoutMs;

                Stopwatch sw = Stopwatch.StartNew();
                ssl = new SslStream(new NetworkStream(sock, true), false,
                    delegate(object s, X509Certificate c, X509Chain ch, SslPolicyErrors e) { return true; });

                bool[] ok = new bool[1];
                SslStream cap = ssl;
                Thread th = new Thread(delegate()
                {
                    // 固定 TLS 1.2：.NET Framework 4.8 上 SslProtocols.None 会直接握手失败，
                    // 而 GitHub / Steam 全线都支持 1.2，钉死最稳。
                    try { cap.AuthenticateAsClient(host, null, SslProtocols.Tls12, false); ok[0] = true; }
                    catch { ok[0] = false; }
                });
                th.IsBackground = true;
                th.Start();
                if (!th.Join(timeoutMs)) { stage = 2; return false; }
                if (!ok[0]) { stage = 2; return false; }

                X509Certificate rc = ssl.RemoteCertificate;
                if (rc == null) { stage = 2; return false; }
                if (!CertMatches(host, new X509Certificate2(rc))) { stage = 2; return false; }

                byte[] req = Encoding.ASCII.GetBytes(
                    "GET / HTTP/1.1\r\nHost: " + host + "\r\nUser-Agent: SteamFast/3.0\r\n" +
                    "Accept: */*\r\nConnection: close\r\n\r\n");
                ssl.Write(req);
                ssl.Flush();

                byte[] buf = new byte[512];
                int n = ssl.Read(buf, 0, buf.Length);
                if (n <= 0) { stage = 3; return false; }
                string head = Encoding.ASCII.GetString(buf, 0, n);
                if (!head.StartsWith("HTTP/")) { stage = 3; return false; }
                int sp = head.IndexOf(' ');
                if (sp < 0 || head.Length < sp + 4) { stage = 3; return false; }
                int code;
                if (!int.TryParse(head.Substring(sp + 1, 3), out code)) { stage = 3; return false; }
                status = code;
                if (code >= 500) { stage = 4; return false; }
                sw.Stop();
                ms = (int)sw.ElapsedMilliseconds;
                return true;
            }
            catch { if (stage == 0) stage = 1; return false; }
            finally
            {
                if (ssl != null) { try { ssl.Close(); } catch { } }
                if (sock != null) { try { sock.Close(); } catch { } }
            }
        }

        private static bool CertMatches(string host, X509Certificate2 cert)
        {
            foreach (string n in GetDnsNames(cert))
                if (NameMatch(host, n)) return true;
            try
            {
                string cn = cert.GetNameInfo(X509NameType.SimpleName, false);
                if (!string.IsNullOrEmpty(cn) && NameMatch(host, cn)) return true;
            }
            catch { }
            return false;
        }

        private static List<string> GetDnsNames(X509Certificate2 cert)
        {
            List<string> list = new List<string>();
            foreach (X509Extension ext in cert.Extensions)
            {
                if (ext.Oid != null && ext.Oid.Value == "2.5.29.17")
                {
                    foreach (string c in ext.Format(false).Split(new char[] { ',', '\r', '\n' }))
                    {
                        string p = c.Trim();
                        if (p.StartsWith("DNS Name=", StringComparison.OrdinalIgnoreCase))
                            list.Add(p.Substring(9).Trim());
                    }
                }
            }
            return list;
        }

        public static bool NameMatch(string host, string pattern)
        {
            if (string.IsNullOrEmpty(host) || string.IsNullOrEmpty(pattern)) return false;
            host = host.Trim().ToLowerInvariant().TrimEnd('.');
            pattern = pattern.Trim().ToLowerInvariant().TrimEnd('.');
            if (pattern == host) return true;
            if (pattern.StartsWith("*."))
            {
                string suffix = pattern.Substring(1);
                if (host.EndsWith(suffix, StringComparison.Ordinal) && host.Length > suffix.Length) return true;
            }
            return false;
        }
    }

    // ========================================================================
    //  域名库
    // ========================================================================
    static class Domains
    {
        public static readonly string[] Steam = new string[]
        {
            "store.steampowered.com", "api.steampowered.com", "login.steampowered.com",
            "checkout.steampowered.com", "help.steampowered.com", "media.steampowered.com",
            "steamcdn-a.akamaihd.net", "steamuserimages-a.akamaihd.net",
            "cdn.akamai.steamstatic.com", "community.akamai.steamstatic.com",
            "store.akamai.steamstatic.com", "avatars.akamai.steamstatic.com",
            "community.steamstatic.com", "steamcommunity-a.akamaihd.net",
            "steamcommunity.com", "www.steamcommunity.com"
        };
        public static readonly string[] Github = new string[]
        {
            "github.com", "api.github.com", "codeload.github.com", "gist.github.com",
            "github.githubassets.com", "collector.github.com", "uploads.github.com",
            "raw.githubusercontent.com", "objects.githubusercontent.com",
            "gist.githubusercontent.com", "camo.githubusercontent.com",
            "user-images.githubusercontent.com", "avatars.githubusercontent.com",
            "media.githubusercontent.com", "raw.github.com", "github.io"
        };
        public static readonly string[] Ai = new string[]
        {
            "huggingface.co", "cdn-lfs.huggingface.co", "cdn-lfs.hf.co", "hf.co",
            "cdn-images.hf.co", "cdn-avatars.huggingface.co"
        };

        public static List<string> Pick(string csv)
        {
            List<string> all = new List<string>();
            foreach (string g in csv.Split(','))
            {
                string k = g.Trim().ToLowerInvariant();
                if (k == "steam") all.AddRange(Steam);
                else if (k == "github") all.AddRange(Github);
                else if (k == "ai") all.AddRange(Ai);
            }
            return all.Distinct().ToList();
        }

        public static List<string> All()
        {
            List<string> all = new List<string>();
            all.AddRange(Steam); all.AddRange(Github); all.AddRange(Ai);
            return all.Distinct().ToList();
        }
    }

    // ========================================================================
    //  hosts 读写
    // ========================================================================
    static class HostsFile
    {
        public static string ReadText(out Encoding enc)
        {
            byte[] raw = File.ReadAllBytes(AppInfo.HostsPath);
            int bom = 0;
            Encoding e;
            if (raw.Length >= 3 && raw[0] == 0xEF && raw[1] == 0xBB && raw[2] == 0xBF)
            { e = new UTF8Encoding(true); bom = 3; }
            else if (raw.Length >= 2 && raw[0] == 0xFF && raw[1] == 0xFE)
            { e = Encoding.Unicode; bom = 2; }
            else
            {
                try { new UTF8Encoding(false, true).GetString(raw); e = new UTF8Encoding(false); }
                catch { e = Encoding.Default; }
            }
            enc = e;
            return e.GetString(raw, bom, raw.Length - bom);
        }

        public static string ReadText() { Encoding e; return ReadText(out e); }

        private static void WriteText(string text, Encoding enc)
        {
            string path = AppInfo.HostsPath;
            FileAttributes attrs = File.GetAttributes(path);
            bool ro = (attrs & FileAttributes.ReadOnly) == FileAttributes.ReadOnly;
            try
            {
                if (ro) File.SetAttributes(path, attrs & ~FileAttributes.ReadOnly);
                byte[] body = enc.GetBytes(text);
                byte[] pre = enc.GetPreamble();
                byte[] all = new byte[pre.Length + body.Length];
                Buffer.BlockCopy(pre, 0, all, 0, pre.Length);
                Buffer.BlockCopy(body, 0, all, pre.Length, body.Length);
                File.WriteAllBytes(path, all);
            }
            finally { if (ro) { try { File.SetAttributes(path, attrs); } catch { } } }
        }

        private static string Norm(string s) { return s.Replace("\r\n", "\n").Replace("\r", "\n"); }

        private static List<string> Strip(List<string> lines)
        {
            List<string> outp = new List<string>();
            bool inB = false;
            foreach (string l in lines)
            {
                string t = l.Trim();
                if (t == AppInfo.StartMark) { inB = true; continue; }
                if (t == AppInfo.EndMark) { inB = false; continue; }
                if (inB) continue;
                outp.Add(l);
            }
            List<string> fin = new List<string>();
            int blanks = 0;
            foreach (string l in outp)
            {
                if (l.Trim().Length == 0) { blanks++; if (blanks > 2) continue; }
                else blanks = 0;
                fin.Add(l);
            }
            while (fin.Count > 0 && fin[fin.Count - 1].Trim().Length == 0) fin.RemoveAt(fin.Count - 1);
            fin.Add("");
            return fin;
        }

        public static bool HasBlock()
        {
            try { return ReadText().Contains(AppInfo.StartMark); } catch { return false; }
        }

        public static bool HasSppBlock()
        {
            try { return ReadText().Contains(AppInfo.SppMark); } catch { return false; }
        }

        public static int PublishedCount()
        {
            try
            {
                List<string> lines = new List<string>(Norm(ReadText()).Split('\n'));
                bool inB = false; int n = 0;
                foreach (string l in lines)
                {
                    string t = l.Trim();
                    if (t == AppInfo.StartMark) { inB = true; continue; }
                    if (t == AppInfo.EndMark) { inB = false; continue; }
                    if (inB && t.Length > 0 && !t.StartsWith("#")) n++;
                }
                return n;
            }
            catch { return 0; }
        }

        public static void EnsureBackup()
        {
            try
            {
                if (!Directory.Exists(AppInfo.BackupDir)) Directory.CreateDirectory(AppInfo.BackupDir);
                if (!File.Exists(AppInfo.OriginalBackup)) File.Copy(AppInfo.HostsPath, AppInfo.OriginalBackup, true);
                File.Copy(AppInfo.HostsPath, AppInfo.BeforeApplyBackup, true);
            }
            catch { }
        }

        public static List<string> BuildBlock(List<string> entries)
        {
            List<string> block = new List<string>();
            block.Add(AppInfo.StartMark);
            block.Add("# 由「" + AppInfo.Title + "」自动生成 · " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            block.Add("# 撤除方法：打开 SteamFast 点「停止加速」，或手动删除本区块全部行");
            foreach (string e in entries) block.Add(e);
            block.Add(AppInfo.EndMark);
            return block;
        }

        public static void Apply(List<string> entries)
        {
            EnsureBackup();
            Encoding enc;
            string text = ReadText(out enc);
            List<string> lines = Strip(new List<string>(Norm(text).Split('\n')));

            List<string> block = BuildBlock(entries);

            int insert = lines.Count;
            for (int i = 0; i < lines.Count; i++)
            {
                string s = lines[i].Trim();
                if (s.Length > 0 && !s.StartsWith("#")) { insert = i; break; }
            }
            while (insert > 0)
            {
                string prev = lines[insert - 1].Trim();
                if (prev.StartsWith("#")) insert--; else break;
            }
            lines.InsertRange(insert, block);
            WriteText(string.Join("\r\n", lines.ToArray()), enc);
        }

        /// <summary>只算不改：把"假如现在加速"之后 hosts 会长什么样，输出成文本供预览/验收。</summary>
        public static string Preview(List<string> entries)
        {
            Encoding enc;
            string text = ReadText(out enc);
            List<string> lines = Strip(new List<string>(Norm(text).Split('\n')));
            List<string> block = BuildBlock(entries);
            int insert = lines.Count;
            for (int i = 0; i < lines.Count; i++)
            {
                string s = lines[i].Trim();
                if (s.Length > 0 && !s.StartsWith("#")) { insert = i; break; }
            }
            while (insert > 0)
            {
                string prev = lines[insert - 1].Trim();
                if (prev.StartsWith("#")) insert--; else break;
            }
            lines.InsertRange(insert, block);
            return string.Join("\r\n", lines.ToArray());
        }

        public static void RemoveBlock()
        {
            Encoding enc;
            string text = ReadText(out enc);
            List<string> lines = Strip(new List<string>(Norm(text).Split('\n')));
            WriteText(string.Join("\r\n", lines.ToArray()), enc);
        }

        public static void RestoreOriginal()
        {
            if (!File.Exists(AppInfo.OriginalBackup)) throw new FileNotFoundException("没有找到原始备份（第一次加速时才会创建）");
            File.Copy(AppInfo.OriginalBackup, AppInfo.HostsPath, true);
        }

        public static void FlushDns()
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("ipconfig", "/flushdns");
                psi.CreateNoWindow = true;
                psi.UseShellExecute = false;
                Process p = Process.Start(psi);
                p.WaitForExit(4000);
            }
            catch { }
        }
    }

    // ========================================================================
    //  加速引擎
    // ========================================================================
    class DomainResult
    {
        public string Domain;
        public string Ip;
        public int Ms;
        public string Note;
        public int Candidates;
        public string SysIp;   // 系统 DNS 给的第一个 IP（用于日志对比）
        public int Status;     // HTTPS 状态码
        public int Tries;      // 实际试过几个候选
        public string BaseIp;  // 现状基线：系统 DNS 的 IP 实测能不能用
        public int BaseMs;
        public int BaseStatus;
        public int Gain;       // 改写后的收益百分比
    }

    static class Engine
    {
        public static List<DomainResult> Run(List<string> domains, Action<int, int, string> onProgress)
        {
            Probe.InitTls();
            List<DomainResult> results = new List<DomainResult>();
            object gate = new object();
            int done = 0;
            int total = domains.Count;
            Semaphore pool = new Semaphore(8, 8);
            List<Thread> threads = new List<Thread>();

            foreach (string d in domains)
            {
                string domain = d;
                Thread t = new Thread(delegate()
                {
                    pool.WaitOne();
                    try
                    {
                        DomainResult r = One(domain);
                        lock (gate)
                        {
                            results.Add(r);
                            done++;
                            if (onProgress != null) { try { onProgress(done, total, domain); } catch { } }
                        }
                    }
                    catch
                    {
                        lock (gate)
                        {
                            results.Add(new DomainResult { Domain = domain, Note = "异常" });
                            done++;
                            if (onProgress != null) { try { onProgress(done, total, domain); } catch { } }
                        }
                    }
                    finally { pool.Release(); }
                });
                t.IsBackground = true;
                t.Start();
                threads.Add(t);
            }
            foreach (Thread t in threads) t.Join();
            return results;
        }

        private static DomainResult One(string domain)
        {
            DomainResult r = new DomainResult { Domain = domain };

            // 1) 候选来源三条腿：系统 DNS → 内置种子 → 公共 DNS（去重保序）
            List<string> sys = Dns.SystemResolve(domain, 1200);
            if (sys.Count > 0) r.SysIp = sys[0];
            List<string> cand = new List<string>();
            foreach (string ip in sys) if (!cand.Contains(ip)) cand.Add(ip);
            foreach (string ip in Seeds.For(domain)) if (!cand.Contains(ip)) cand.Add(ip);
            foreach (string ip in Dns.Resolve(domain, 1200)) if (!cand.Contains(ip)) cand.Add(ip);

            List<string> ips = cand.Where(delegate(string x)
            {
                if (x == "127.0.0.1" || x == "0.0.0.0") return false;
                if (x.StartsWith("10.") || x.StartsWith("192.168.") || x.StartsWith("172.16.")) return false;
                return true;
            }).Take(12).ToList();
            r.Candidates = ips.Count;
            if (ips.Count == 0) { r.Note = "DNS 无结果（疑似被污染），跳过"; return r; }

            // 2) 先量出"现状基线"：系统 DNS 给的 IP 现在到底能不能打开、有多快。
            //    基线有两个用途：① 当参照，判断候选 IP 返回的状态码是否正常；
            //                    ② 当尺子，判断这次改写到底值不值得做。
            int baseMs = 0, baseCode = 0, baseStage = 0;
            string baseIp = null;
            foreach (string ip in sys)
            {
                if (Probe.HttpCheck(domain, ip, 3000, out baseMs, out baseCode, out baseStage))
                { baseIp = ip; break; }
            }
            r.BaseIp = baseIp; r.BaseMs = baseMs; r.BaseStatus = baseCode;

            // 3) TCP 测速排序（便宜、并发），只对最快的几个做深度校验
            int[] ms = new int[ips.Count];
            for (int i = 0; i < ms.Length; i++) ms[i] = -1;
            Thread[] ths = new Thread[ips.Count];
            for (int i = 0; i < ips.Count; i++)
            {
                int idx = i;
                ths[i] = new Thread(delegate() { ms[idx] = Probe.TcpMs(ips[idx], 443, 1200); });
                ths[i].IsBackground = true;
                ths[i].Start();
            }
            foreach (Thread t in ths) t.Join(2000);

            List<int> order = new List<int>();
            for (int i = 0; i < ips.Count; i++) if (ms[i] >= 0) order.Add(i);
            if (order.Count == 0)
            {
                r.Note = (baseIp != null) ? "现状可用，候选 IP 全部不可达，保持原样"
                                          : "IP 层全部不可达（TCP 无响应），hosts 无解，需完整反代";
                return r;
            }
            order.Sort(delegate(int a, int b) { return ms[a].CompareTo(ms[b]); });

            // 4) 深度校验：TCP → TLS 证书 → 真实 HTTPS 状态码，且状态码要与基线同类。
            //    只认"能真打开"的 IP；状态码跟基线不同类的（例如基线 200、它返回 403）
            //    说明是错的边缘节点，写进去会把页面搞坏，一律不认。
            int bestMs = int.MaxValue, bestCode = 0;
            string bestIp = null;
            int tried = 0;
            bool stageTls = false, stageHttp = false, stage5xx = false, stageMismatch = false;
            foreach (int idx in order)
            {
                if (tried >= 4) break;
                tried++;
                int total, code, stage;
                if (!Probe.HttpCheck(domain, ips[idx], 3000, out total, out code, out stage))
                {
                    if (stage == 2) stageTls = true;
                    else if (stage == 3) stageHttp = true;
                    else if (stage == 4) stage5xx = true;
                    continue;
                }
                if (baseIp != null && !SameClass(baseCode, code)) { stageMismatch = true; continue; }
                if (baseIp == null && code >= 400) { stageMismatch = true; continue; }
                if (total < bestMs) { bestMs = total; bestIp = ips[idx]; bestCode = code; }
            }
            r.Tries = tried;

            if (bestIp == null)
            {
                if (baseIp != null) r.Note = "现状可用，候选都不如它，保持原样";
                else if (stageTls) r.Note = "TLS 被重置/超时（SNI 层封锁），hosts 无解，需完整反代";
                else if (stageHttp) r.Note = "能握手但请求无响应，跳过";
                else if (stage5xx) r.Note = "源站返回 5xx，跳过";
                else if (stageMismatch) r.Note = "候选返回异常状态码，跳过";
                else r.Note = "候选全部不可用，跳过";
                return r;
            }

            // 5) 收益判据：只有明显更快才改写。写了却不快，等于白折腾还添风险。
            if (baseIp != null)
            {
                if (baseIp == bestIp) { r.Note = "系统 DNS 已是最优，无需改写"; return r; }
                r.Gain = (int)Math.Round((1.0 - (double)bestMs / baseMs) * 100);
                if (baseMs - bestMs < 80)
                {
                    r.Note = "改写收益太小（原 " + baseMs + "ms / 优 " + bestMs + "ms），保持原样";
                    return r;
                }
            }

            r.Ip = bestIp;
            r.Ms = bestMs;
            r.Status = bestCode;
            r.Note = (baseIp == null) ? "基线打不开，候选可用" : "比现状快 " + r.Gain + "%";
            return r;
        }

        private static bool SameClass(int a, int b)
        {
            if (a >= 500 || b >= 500) return false;
            return (a < 400) == (b < 400);
        }
    }

    // ========================================================================
    //  工作进程（带 --job / --stop / --restore / --diagnose / --auto 等参数时走这里）
    // ========================================================================
    static class Worker
    {
        private static string _progress;
        private static string _result;

        private static void Prog(string text)
        {
            string line = DateTime.Now.ToString("HH:mm:ss") + "  " + text;
            try
            {
                string d = Path.GetDirectoryName(_progress);
                if (!string.IsNullOrEmpty(d) && !Directory.Exists(d)) Directory.CreateDirectory(d);
                File.AppendAllText(_progress, line + "\r\n", new UTF8Encoding(false));
            }
            catch { }
            Log.W(text);
        }

        private static void Result(string status, string detail, int count, bool verified)
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("status=" + status);
            sb.AppendLine("count=" + count);
            sb.AppendLine("verified=" + (verified ? "True" : "False"));
            sb.AppendLine("detail=" + detail);
            sb.AppendLine("time=" + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            try { File.WriteAllText(_result, sb.ToString(), new UTF8Encoding(false)); } catch { }
        }

        private static bool IsAdmin()
        {
            try
            {
                System.Security.Principal.WindowsIdentity id = System.Security.Principal.WindowsIdentity.GetCurrent();
                return new System.Security.Principal.WindowsPrincipal(id)
                    .IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
            }
            catch { return false; }
        }

        private static Dictionary<string, string> ReadJob(string path)
        {
            Dictionary<string, string> job = new Dictionary<string, string>();
            try
            {
                if (!string.IsNullOrEmpty(path) && File.Exists(path))
                {
                    foreach (string l in File.ReadAllLines(path))
                    {
                        int i = l.IndexOf('=');
                        if (i > 0) job[l.Substring(0, i).Trim()] = l.Substring(i + 1).Trim();
                    }
                }
            }
            catch { }
            if (!job.ContainsKey("groups")) job["groups"] = "steam,github,ai";
            if (!job.ContainsKey("mode")) job["mode"] = "direct";
            if (!job.ContainsKey("source")) job["source"] = "命令行";
            return job;
        }

        private static int RunSchtasks(string args)
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("schtasks", args);
                psi.CreateNoWindow = true; psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true; psi.RedirectStandardError = true;
                Process p = Process.Start(psi);
                p.StandardOutput.ReadToEnd(); p.StandardError.ReadToEnd();
                p.WaitForExit(20000);
                return p.ExitCode;
            }
            catch { return -1; }
        }

        public static void Run(string[] args)
        {
            string jobFile = Arg(args, "--job");
            bool stop = Flag(args, "--stop");
            bool restore = Flag(args, "--restore");
            bool diag = Flag(args, "--diagnose");
            bool preview = Flag(args, "--preview");
            bool installAuto = Flag(args, "--install-auto");
            bool removeAuto = Flag(args, "--remove-auto");
            bool auto = Flag(args, "--auto");

            if (!string.IsNullOrEmpty(jobFile))
            {
                _progress = jobFile + ".progress";
                _result = jobFile + ".result";
            }
            else
            {
                string baseName = auto ? "auto" : "job";
                _progress = Path.Combine(AppInfo.LogDir, baseName + ".progress");
                _result = Path.Combine(AppInfo.LogDir, baseName + ".result");
            }
            try { if (File.Exists(_progress)) File.Delete(_progress); } catch { }
            try { if (File.Exists(_result)) File.Delete(_result); } catch { }

            Dictionary<string, string> job = ReadJob(jobFile);
            if (auto) { job["groups"] = "steam,github,ai"; job["mode"] = "direct"; job["source"] = "开机自启"; }

            // ---------------- 停止
            if (stop)
            {
                Prog("收到「停止加速」指令");
                try
                {
                    if (!HostsFile.HasBlock())
                    {
                        Prog("当前 hosts 中没有 SteamFast 区块，无需停止");
                        Result("ok", "本来就没有加速", 0, true);
                        return;
                    }
                    int old = HostsFile.PublishedCount();
                    HostsFile.RemoveBlock();
                    HostsFile.FlushDns();
                    bool still = HostsFile.HasBlock();
                    if (still) { Prog("移除后回读仍有残留"); Result("error", "移除不彻底，可能被安全软件挡了", 0, false); }
                    else
                    {
                        Prog("已移除 " + old + " 条记录并刷新 DNS");
                        Result("ok", "已停止加速（Steam++ 的条目未受影响）", 0, true);
                    }
                }
                catch (Exception ex) { Prog("停止失败：" + ex.Message); Result("error", ex.Message, 0, false); }
                return;
            }

            // ---------------- 还原
            if (restore)
            {
                Prog("收到「还原 hosts」指令");
                try
                {
                    HostsFile.RestoreOriginal();
                    HostsFile.FlushDns();
                    Prog("hosts 已还原为最初的备份内容");
                    Result("ok", "已还原 hosts", 0, true);
                }
                catch (Exception ex) { Prog("还原失败：" + ex.Message); Result("error", ex.Message, 0, false); }
                return;
            }

            // ---------------- 只测速
            if (diag)
            {
                Prog("开始详细测速（只测不改，不动 hosts）");
                try
                {
                    List<string> doms = Domains.Pick(job["groups"]);
                    if (doms.Count == 0) throw new Exception("没有选中任何域名分组");
                    Prog("待测域名 " + doms.Count + " 个");
                    List<DomainResult> res = Engine.Run(doms, delegate(int d, int t, string dom)
                    {
                        Prog("  进度 " + d + "/" + t + " — " + dom);
                    });
                    int ok = 0, skip = 0, nohosts = 0, keep = 0;
                    foreach (DomainResult r in res.OrderBy(delegate(DomainResult x) { return x.Domain; }))
                    {
                        if (r.Ip != null) ok++;
                        else
                        {
                            skip++;
                            if (r.Note != null && r.Note.IndexOf("hosts 无解") >= 0) nohosts++;
                            if (r.Note != null && r.Note.IndexOf("保持原样") >= 0) keep++;
                        }
                        Prog((r.Ip != null ? "  √ " : "  × ") + Pad(r.Domain, 38) + " " + Desc(r));
                    }
                    Prog("测速完成：值得改写 " + ok + " 个 / 不改 " + skip + " 个（其中 hosts 无解 " + nohosts +
                         " 个、现状已够快 " + keep + " 个）");
                    Result("ok", "测速完成：值得改写 " + ok + " 个，不改 " + skip + " 个（hosts 无解 " + nohosts + " 个）", ok, true);
                }
                catch (Exception ex) { Prog("测速失败：" + ex.Message); Result("error", ex.Message, 0, false); }
                return;
            }

            // ---------------- 只预览：算出"该写什么"，输出到 logs\hosts_preview.txt，不动 hosts
            if (preview)
            {
                Prog("开始生成 hosts 预览（不动真实 hosts）");
                try
                {
                    List<string> doms = Domains.Pick(job["groups"]);
                    if (doms.Count == 0) throw new Exception("没有选中任何域名分组");
                    List<DomainResult> res = Engine.Run(doms, null);
                    List<string> entries = new List<string>();
                    foreach (DomainResult r in res.OrderBy(delegate(DomainResult x) { return x.Domain; }))
                        if (r.Ip != null) entries.Add(Pad(r.Ip, 16) + r.Domain);

                    string txt = HostsFile.Preview(entries);
                    string outFile = Path.Combine(AppInfo.LogDir, "hosts_preview.txt");
                    File.WriteAllText(outFile, txt, new UTF8Encoding(false));

                    int inside = 0; bool inB = false;
                    foreach (string l in txt.Split('\n'))
                    {
                        string t = l.Trim();
                        if (t == AppInfo.StartMark) { inB = true; continue; }
                        if (t == AppInfo.EndMark) { inB = false; continue; }
                        if (inB && t.Length > 0 && !t.StartsWith("#")) inside++;
                    }
                    Prog("预览已生成：" + outFile);
                    Prog("区块内有效条目 " + inside + " 条（去重后应等于 " + entries.Count + "）");
                    Result("ok", "预览已生成，区块 " + inside + " 条", inside, true);
                }
                catch (Exception ex) { Prog("预览失败：" + ex.Message); Result("error", ex.Message, 0, false); }
                return;
            }

            // ---------------- 开机自启
            if (installAuto || removeAuto)
            {
                if (removeAuto)
                {
                    Prog("正在取消开机自动加速…");
                    int rc = RunSchtasks("/delete /tn \"" + AppInfo.TaskName + "\" /f");
                    Prog("schtasks 返回码 " + rc);
                    Result(rc == 0 ? "ok" : "error", rc == 0 ? "已取消开机自动加速" : "取消失败（返回码 " + rc + "）", 0, rc == 0);
                    return;
                }
                Prog("正在设置开机自动加速…");
                string tr = "\"" + AppInfo.ExePath + "\" --auto";
                int rc2 = RunSchtasks("/create /tn \"" + AppInfo.TaskName + "\" /tr \"" + tr +
                                      "\" /sc onlogon /rl highest /f");
                Prog("schtasks 返回码 " + rc2);
                int rcq = RunSchtasks("/query /tn \"" + AppInfo.TaskName + "\"");
                bool okc = (rc2 == 0 && rcq == 0);
                Result(okc ? "ok" : "error",
                       okc ? "已设置开机自动加速（登录后静默执行，不弹窗）" : "计划任务创建失败（返回码 " + rc2 + "）",
                       0, okc);
                return;
            }

            // ---------------- 正常加速
            try
            {
                string mode = job["mode"];
                bool doDirect = (mode == "direct" || mode == "both");
                bool doFull = (mode == "full" || mode == "both");
                Prog("开始加速（来源：" + job["source"] + "，模式：" + mode + "）");

                int written = 0;
                bool verified = false;

                if (doDirect)
                {
                    List<string> doms = Domains.Pick(job["groups"]);
                    if (doms.Count == 0) throw new Exception("没有选中任何域名分组");
                    Prog("待优选域名 " + doms.Count + " 个，正在多源 DNS 解析并做 TCP + TLS 双验证…");
                    List<DomainResult> res = Engine.Run(doms, delegate(int d, int t, string dom)
                    {
                        Prog("  进度 " + d + "/" + t + " — " + dom);
                    });

                    List<string> entries = new List<string>();
                    int nohosts = 0;
                    foreach (DomainResult r in res.OrderBy(delegate(DomainResult x) { return x.Domain; }))
                    {
                        if (r.Ip != null) entries.Add(Pad(r.Ip, 16) + r.Domain);
                        else if (r.Note != null && r.Note.IndexOf("hosts 无解") >= 0) nohosts++;
                    }
                    Prog("值得改写 " + entries.Count + " / " + doms.Count + " 个域名");
                    foreach (DomainResult r in res.OrderBy(delegate(DomainResult x) { return x.Domain; }))
                    {
                        Prog((r.Ip != null ? "  √ " : "  × ") + Pad(r.Domain, 38) + " " + Desc(r));
                    }
                    if (nohosts > 0)
                    {
                        Prog("提示：" + nohosts + " 个域名属 TLS(SNI) 层封锁，hosts 方案对它们无效，");
                        Prog("      GitHub 的 raw 内容与 Release 下载需要「完整反代」模式（Watt Toolkit / 代理）。");
                    }

                    if (entries.Count == 0)
                    {
                        Prog("没有任何可用直连 IP，hosts 未改动");
                        Result("error", "所有域名都没有可用直连，请改用「完整反代」模式", 0, false);
                        return;
                    }

                    HostsFile.Apply(entries);
                    HostsFile.FlushDns();
                    Thread.Sleep(300);
                    int after = HostsFile.PublishedCount();
                    verified = (HostsFile.HasBlock() && after >= entries.Count);
                    if (verified) Prog("已写入 hosts 并通过回读校验（" + after + " 条），DNS 缓存已刷新");
                    else Prog("!! 写入后回读校验不通过：hosts 可能被安全软件改回去了");
                    written = after;
                }

                if (doFull)
                {
                    Prog("正在唤起 Watt Toolkit / Steam++ …");
                    try
                    {
                        bool running = false;
                        foreach (Process p in Process.GetProcesses())
                        {
                            try { if (p.ProcessName.StartsWith("Steam++", StringComparison.OrdinalIgnoreCase)) { running = true; break; } }
                            catch { }
                        }
                        if (running) Prog("Watt Toolkit 已在运行，无需重复启动");
                        else
                        {
                            Process.Start("explorer.exe", AppInfo.SppAppsFolder);
                            Prog("已发出启动指令，Steam++ 起来后会自己开启它的网络反代");
                        }
                    }
                    catch (Exception ex) { Prog("唤起失败：" + ex.Message); }
                }

                string detail = doDirect ? ("直连优选生效 " + written + " 条") : "已唤起 Watt Toolkit（完整反代）";
                if (doDirect && doFull) detail += "；已唤起 Watt Toolkit";
                Result("ok", detail, written, verified);
                Prog("完成");
            }
            catch (Exception ex)
            {
                Prog("!! 出错：" + ex.Message);
                Result("error", ex.Message, 0, false);
            }
        }

        private static string Desc(DomainResult r)
        {
            if (r.Ip == null)
            {
                string s = r.Note;
                if (r.BaseIp != null) s += "（现状 " + r.BaseIp + "  " + r.BaseMs + "ms）";
                else if (r.SysIp != null) s += "（系统 DNS: " + r.SysIp + "）";
                return s;
            }
            string t = "→ " + Pad(r.Ip, 16) + Pad(r.Ms + "ms", 8) + "HTTP " + r.Status;
            if (r.BaseIp != null) t += "   原 " + Pad(r.BaseIp, 16) + r.BaseMs + "ms → 快 " + r.Gain + "%";
            else t += "   （基线打不开，改用此 IP）";
            return t;
        }

        public static string Pad(string s, int n)
        {
            while (s.Length < n) s += " ";
            return s;
        }

        private static bool Flag(string[] args, string name)
        {
            foreach (string a in args) if (string.Equals(a, name, StringComparison.OrdinalIgnoreCase)) return true;
            return false;
        }

        private static string Arg(string[] args, string name)
        {
            for (int i = 0; i < args.Length - 1; i++)
                if (string.Equals(args[i], name, StringComparison.OrdinalIgnoreCase)) return args[i + 1];
            return null;
        }
    }

    // ========================================================================
    //  圆角按钮（Panel + Region + 自绘）
    // ========================================================================
    class RoundPanel : Panel
    {
        public Color NormalColor;
        public Color HoverColor;
        public Color DownColor;
        public Color LabelColor = Color.White;
        public int Radius = 10;
        private bool _hover, _down;

        public RoundPanel()
        {
            SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
                     ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
            Font = new Font("Microsoft YaHei UI", 13F, FontStyle.Bold);
            Cursor = Cursors.Hand;
        }

        public void RebuildRegion(double k)
        {
            int r = (int)Math.Round(Radius * k);
            int d = r * 2;
            if (d > Height) d = Height;
            if (d < 2) d = 2;
            using (GraphicsPath gp = new GraphicsPath())
            {
                gp.AddArc(0, 0, d, d, 180, 90);
                gp.AddArc(Width - d - 1, 0, d, d, 270, 90);
                gp.AddArc(Width - d - 1, Height - d - 1, d, d, 0, 90);
                gp.AddArc(0, Height - d - 1, d, d, 90, 90);
                gp.CloseFigure();
                Region = new Region(gp);
            }
        }

        protected override void OnMouseEnter(EventArgs e) { _hover = true; Invalidate(); base.OnMouseEnter(e); }
        protected override void OnMouseLeave(EventArgs e) { _hover = false; _down = false; Invalidate(); base.OnMouseLeave(e); }
        protected override void OnMouseDown(MouseEventArgs e) { _down = true; Invalidate(); base.OnMouseDown(e); }
        protected override void OnMouseUp(MouseEventArgs e) { _down = false; Invalidate(); base.OnMouseUp(e); }

        protected override void OnPaint(PaintEventArgs pe)
        {
            Graphics g = pe.Graphics;
            g.SmoothingMode = SmoothingMode.AntiAlias;
            g.Clear(Parent != null ? Parent.BackColor : Color.White);
            Color c = (_down ? DownColor : (_hover ? HoverColor : NormalColor));
            using (SolidBrush b = new SolidBrush(c))
                g.FillPath(b, Round(new Rectangle(0, 0, Width - 1, Height - 1), Radius));
            TextRenderer.DrawText(g, Text, Font, new Rectangle(0, 0, Width, Height), LabelColor,
                TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
        }

        private static GraphicsPath Round(Rectangle r, int radius)
        {
            int d = radius * 2;
            if (d > r.Height) d = r.Height;
            if (d < 2) d = 2;
            GraphicsPath p = new GraphicsPath();
            p.AddArc(r.X, r.Y, d, d, 180, 90);
            p.AddArc(r.Right - d, r.Y, d, d, 270, 90);
            p.AddArc(r.Right - d, r.Bottom - d, d, d, 0, 90);
            p.AddArc(r.X, r.Bottom - d, d, d, 90, 90);
            p.CloseFigure();
            return p;
        }
    }

    class Dot : Control
    {
        public Color DotColor = Color.FromArgb(150, 160, 170);
        public Dot()
        {
            SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
                     ControlStyles.OptimizedDoubleBuffer | ControlStyles.ResizeRedraw, true);
            Size = new Size(16, 16);
        }
        protected override void OnPaint(PaintEventArgs e)
        {
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            e.Graphics.Clear(Parent != null ? Parent.BackColor : Color.White);
            using (SolidBrush b = new SolidBrush(DotColor))
                e.Graphics.FillEllipse(b, 0, 0, Width - 1, Height - 1);
        }
    }

    // ========================================================================
    //  主界面
    // ========================================================================
    class MainForm : Form
    {
        static readonly Color C_Header = Color.FromArgb(27, 40, 56);
        static readonly Color C_Accent = Color.FromArgb(102, 192, 244);
        static readonly Color C_Status = Color.FromArgb(240, 245, 249);
        static readonly Color C_Text = Color.FromArgb(27, 40, 56);
        static readonly Color C_Sub = Color.FromArgb(96, 112, 128);
        static readonly Color C_Line = Color.FromArgb(219, 228, 236);
        static readonly Color C_Green = Color.FromArgb(46, 170, 110);
        static readonly Color C_Amber = Color.FromArgb(226, 158, 42);
        static readonly Color C_Red = Color.FromArgb(214, 78, 68);
        static readonly Color C_Grey = Color.FromArgb(150, 160, 170);
        static readonly Color C_BigNormal = Color.FromArgb(38, 122, 176);
        static readonly Color C_BigHover = Color.FromArgb(52, 145, 205);
        static readonly Color C_BigOff = Color.FromArgb(186, 196, 206);
        static readonly Color C_BtnBg = Color.FromArgb(238, 243, 248);

        private double _k = 1.0;
        private Dot _dot;
        private Label _statusMain, _statusSub;
        private RoundPanel _big;
        private RadioButton _rbDirect, _rbFull, _rbBoth;
        private CheckBox _ckSteam, _ckGit, _ckAi;
        private TextBox _log;
        private Button _btnAuto;
        private bool _busy;
        private string _jobFile;
        private string _jobKind = "";
        private string _progressPath, _resultPath;
        private long _progressLen;
        private System.Windows.Forms.Timer _timer;

        public MainForm()
        {
            _k = ComputeScale();
            BuildUi();
            Shown += delegate { OnShownFirst(); };
        }

        // ------------------------------------------------------ DPI
        private static double ComputeScale()
        {
            try
            {
                using (Graphics g = Graphics.FromHwnd(IntPtr.Zero))
                {
                    double k = g.DpiX / 96.0;
                    if (k < 1.0) k = 1.0;
                    if (k > 3.0) k = 3.0;
                    return k;
                }
            }
            catch { return 1.0; }
        }

        private void ScaleAll(Control parent, double k)
        {
            foreach (Control c in parent.Controls)
            {
                c.Location = new Point((int)Math.Round(c.Left * k), (int)Math.Round(c.Top * k));
                c.Size = new Size((int)Math.Round(c.Width * k), (int)Math.Round(c.Height * k));
                if (c.Controls.Count > 0) ScaleAll(c, k);
            }
        }

        // ------------------------------------------------------ UI
        private void BuildUi()
        {
            Text = AppInfo.Title + "  v" + AppInfo.Version;
            Font = new Font("Microsoft YaHei UI", 10F);
            BackColor = Color.White;
            ClientSize = new Size(720, 626);
            FormBorderStyle = FormBorderStyle.FixedSingle;
            MaximizeBox = false;
            StartPosition = FormStartPosition.CenterScreen;
            AutoScaleMode = AutoScaleMode.None;

            string ico = Path.Combine(AppInfo.Dir, "SteamFast.ico");
            try { if (File.Exists(ico)) Icon = new Icon(ico); } catch { }

            Panel header = new Panel();
            header.Location = new Point(0, 0);
            header.Size = new Size(720, 86);
            header.BackColor = C_Header;
            Controls.Add(header);

            Label t1 = new Label();
            t1.Text = "蒸汽快线";
            t1.Font = new Font("Microsoft YaHei UI", 20F, FontStyle.Bold);
            t1.ForeColor = Color.White;
            t1.AutoSize = true;
            t1.BackColor = Color.Transparent;
            t1.Location = new Point(26, 12);
            header.Controls.Add(t1);

            Label t2 = new Label();
            t2.Text = "SteamFast  ·  零证书  ·  零常驻  ·  只钉真能打开的 IP  ·  关掉窗口也继续生效";
            t2.Font = new Font("Microsoft YaHei UI", 10F);
            t2.ForeColor = C_Accent;
            t2.AutoSize = true;
            t2.BackColor = Color.Transparent;
            t2.Location = new Point(29, 52);
            header.Controls.Add(t2);

            Label ver = new Label();
            ver.Text = "v" + AppInfo.Version;
            ver.Font = new Font("Consolas", 9F);
            ver.ForeColor = Color.FromArgb(110, 130, 150);
            ver.AutoSize = true;
            ver.BackColor = Color.Transparent;
            ver.Location = new Point(648, 16);
            header.Controls.Add(ver);

            Panel sp = new Panel();
            sp.Location = new Point(0, 86);
            sp.Size = new Size(720, 56);
            sp.BackColor = C_Status;
            sp.Paint += delegate(object s, PaintEventArgs e)
            {
                using (Pen p = new Pen(C_Line)) e.Graphics.DrawLine(p, 0, sp.Height - 1, sp.Width, sp.Height - 1);
            };
            Controls.Add(sp);

            _dot = new Dot();
            _dot.Location = new Point(28, 20);
            sp.Controls.Add(_dot);

            _statusMain = new Label();
            _statusMain.Text = "正在检测…";
            _statusMain.Font = new Font("Microsoft YaHei UI", 12.5F, FontStyle.Bold);
            _statusMain.ForeColor = C_Text;
            _statusMain.AutoSize = true;
            _statusMain.BackColor = Color.Transparent;
            _statusMain.Location = new Point(54, 9);
            sp.Controls.Add(_statusMain);

            _statusSub = new Label();
            _statusSub.Text = "";
            _statusSub.Font = new Font("Microsoft YaHei UI", 9.5F);
            _statusSub.ForeColor = C_Sub;
            _statusSub.AutoSize = true;
            _statusSub.BackColor = Color.Transparent;
            _statusSub.Location = new Point(56, 31);
            sp.Controls.Add(_statusSub);

            _big = new RoundPanel();
            _big.Text = "一键加速";
            _big.Location = new Point(26, 158);
            _big.Size = new Size(668, 58);
            _big.NormalColor = C_BigNormal;
            _big.HoverColor = C_BigHover;
            _big.DownColor = Color.FromArgb(28, 100, 148);
            _big.Font = new Font("Microsoft YaHei UI", 14F, FontStyle.Bold);
            _big.Click += delegate { if (!_busy) StartAccel(); };
            Controls.Add(_big);

            AddSection("加速模式", 232);
            _rbDirect = AddRadio("直连优选（推荐）  不装证书、不设代理、不常驻后台", 26, 256, true);
            _rbFull = AddRadio("完整反代  唤起已装的 Watt Toolkit / Steam++，覆盖商店与社区整页", 26, 280, false);
            _rbBoth = AddRadio("双引擎  先直连优选，再唤起 Watt Toolkit（覆盖面最广）", 26, 304, false);

            AddSection("加速范围", 334);
            _ckSteam = AddCheck("Steam 商店 / 社区 / CDN", 26, 358, true);
            _ckGit = AddCheck("GitHub 主站 / API", 286, 358, true);
            _ckAi = AddCheck("Hugging Face / AI 资源", 500, 358, true);

            AddSection("运行日志", 394);

            _log = new TextBox();
            _log.Location = new Point(26, 416);
            _log.Size = new Size(668, 150);
            _log.Multiline = true;
            _log.ReadOnly = true;
            _log.ScrollBars = ScrollBars.Vertical;
            _log.BackColor = Color.FromArgb(22, 32, 44);
            _log.ForeColor = Color.FromArgb(206, 232, 250);
            _log.BorderStyle = BorderStyle.None;
            _log.Font = new Font("Consolas", 10F);
            Controls.Add(_log);

            int y = 584, w = 105, gap = 7, x = 26;
            Button b1 = AddBtn("停止加速", x, y, w); x += w + gap;
            b1.Click += delegate { if (!_busy) StopAccel(); };
            Button b2 = AddBtn("详细测速", x, y, w); x += w + gap;
            b2.Click += delegate { if (!_busy) Diagnose(); };
            Button b3 = AddBtn("还原 hosts", x, y, w); x += w + gap;
            b3.Click += delegate { if (!_busy) RestoreHosts(); };
            _btnAuto = AddBtn("开机自启", x, y, w); x += w + gap;
            _btnAuto.Click += delegate { if (!_busy) ToggleAutostart(); };
            Button b5 = AddBtn("安装目录", x, y, w); x += w + gap;
            b5.Click += delegate { try { Process.Start("explorer.exe", AppInfo.Dir); } catch { } };
            Button b6 = AddBtn("退出", x, y, w);
            b6.Click += delegate { Close(); };

            // ---- DPI 等比放大 ----
            if (_k != 1.0)
            {
                ClientSize = new Size((int)Math.Round(720 * _k), (int)Math.Round(626 * _k));
                ScaleAll(this, _k);
                _big.RebuildRegion(_k);
            }

            _timer = new System.Windows.Forms.Timer();
            _timer.Interval = 700;
            _timer.Tick += delegate { Poll(); };

            FormClosing += delegate(object s, FormClosingEventArgs e)
            {
                if (_busy)
                {
                    if (MessageBox.Show(this, "正在处理中，确定要关闭吗？", AppInfo.Title,
                        MessageBoxButtons.YesNo, MessageBoxIcon.Question) != DialogResult.Yes)
                    { e.Cancel = true; return; }
                }
                _timer.Stop();
                Log.W("主界面关闭");
            };
        }

        private void AddSection(string text, int y)
        {
            Label l = new Label();
            l.Text = text;
            l.Font = new Font("Microsoft YaHei UI", 10F, FontStyle.Bold);
            l.ForeColor = C_Sub;
            l.AutoSize = true;
            l.Location = new Point(26, y);
            Controls.Add(l);
        }

        private RadioButton AddRadio(string text, int x, int y, bool chk)
        {
            RadioButton r = new RadioButton();
            r.Text = text; r.AutoSize = true; r.Checked = chk;
            r.Location = new Point(x, y); r.ForeColor = C_Text;
            Controls.Add(r);
            return r;
        }

        private CheckBox AddCheck(string text, int x, int y, bool chk)
        {
            CheckBox c = new CheckBox();
            c.Text = text; c.AutoSize = true; c.Checked = chk;
            c.Location = new Point(x, y); c.ForeColor = C_Text;
            Controls.Add(c);
            return c;
        }

        private Button AddBtn(string text, int x, int y, int w)
        {
            Button b = new Button();
            b.Text = text;
            b.Location = new Point(x, y);
            b.Size = new Size(w, 32);
            b.FlatStyle = FlatStyle.Flat;
            b.BackColor = C_BtnBg;
            b.ForeColor = C_Text;
            b.FlatAppearance.BorderColor = C_Line;
            b.FlatAppearance.BorderSize = 1;
            b.FlatAppearance.MouseOverBackColor = C_Accent;
            b.Cursor = Cursors.Hand;
            Controls.Add(b);
            return b;
        }

        // ------------------------------------------------------ 启动初始化
        private void OnShownFirst()
        {
            AppendLog("=== " + AppInfo.Title + " v" + AppInfo.Version + " ===");
            AppendLog("程序目录：" + AppInfo.Dir);
            AppendLog("hosts   ：" + AppInfo.HostsPath);
            AppendLog("屏幕缩放：" + (int)(_k * 100) + "%，界面已按同一比例放大");
            AppendLog("就绪。点「一键加速」时才会弹一次管理员确认（改 hosts 必须提权）。");
            Log.W("主界面启动，缩放 " + (int)(_k * 100) + "%");
            Probe.InitTls();
            RefreshStatus();
            UpdateAutoButton();
        }

        private bool IsAdmin()
        {
            try
            {
                System.Security.Principal.WindowsIdentity id = System.Security.Principal.WindowsIdentity.GetCurrent();
                return new System.Security.Principal.WindowsPrincipal(id)
                    .IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
            }
            catch { return false; }
        }

        private void SetStatus(string main, string sub, Color color)
        {
            if (main != null) _statusMain.Text = main;
            _dot.DotColor = color;
            _dot.Invalidate();
            if (sub != null) _statusSub.Text = sub;
        }

        private void SetBig(bool on, string text)
        {
            if (text != null) _big.Text = text;
            _big.NormalColor = on ? C_BigNormal : C_BigOff;
            _big.HoverColor = on ? C_BigHover : C_BigOff;
            _big.Cursor = on ? Cursors.Hand : Cursors.Default;
            _big.Invalidate();
        }

        private void UpdateAutoButton()
        {
            try
            {
                ProcessStartInfo psi = new ProcessStartInfo("schtasks", "/query /tn \"" + AppInfo.TaskName + "\"");
                psi.CreateNoWindow = true; psi.UseShellExecute = false;
                psi.RedirectStandardOutput = true; psi.RedirectStandardError = true;
                Process p = Process.Start(psi);
                p.StandardOutput.ReadToEnd(); p.StandardError.ReadToEnd();
                p.WaitForExit(6000);
                bool has = p.ExitCode == 0;
                _btnAuto.Text = has ? "开机自启 已开" : "开机自启";
                _btnAuto.ForeColor = has ? Color.FromArgb(46, 140, 200) : C_Text;
            }
            catch { }
        }

        private void RefreshStatus()
        {
            try
            {
                if (HostsFile.HasBlock() && HostsFile.PublishedCount() > 0)
                {
                    SetStatus("已加速 · 生效中",
                        "hosts 里有 " + HostsFile.PublishedCount() + " 条优选记录，关掉窗口也生效" +
                        (HostsFile.HasSppBlock() ? "  · Steam++ 优先级更低" : ""), C_Green);
                    SetBig(true, "重新测速并加速");
                }
                else if (HostsFile.HasBlock())
                {
                    SetStatus("已加速（0 条有效）", "区块存在但没有有效条目，建议重新加速", C_Amber);
                    SetBig(true, "重新测速并加速");
                }
                else
                {
                    SetStatus("未加速", "点下面的「一键加速」即可开始" +
                        (HostsFile.HasSppBlock() ? "  · Steam++ 优先级更低" : ""), C_Grey);
                    SetBig(true, "一键加速");
                }
            }
            catch (Exception ex)
            {
                SetStatus("读取 hosts 失败", ex.Message, C_Red);
            }
        }

        private void AppendLog(string line)
        {
            if (_log.InvokeRequired) { try { _log.Invoke(new Action<string>(AppendLog), line); } catch { } return; }
            _log.AppendText(line + "\r\n");
            _log.SelectionStart = _log.TextLength;
            _log.ScrollToCaret();
        }

        // ------------------------------------------------------ 起工作进程
        private bool StartWorker(string args, bool elevate)
        {
            ProcessStartInfo psi = new ProcessStartInfo(AppInfo.ExePath, args);
            psi.UseShellExecute = true;
            psi.WindowStyle = ProcessWindowStyle.Hidden;
            if (elevate) psi.Verb = "runas";
            try
            {
                Process.Start(psi);
                return true;
            }
            catch (Exception ex)
            {
                AppendLog("!! 启动工作进程失败：" + ex.Message);
                if (ex.Message.IndexOf("cancel", StringComparison.OrdinalIgnoreCase) >= 0 ||
                    ex.Message.IndexOf("取消", StringComparison.OrdinalIgnoreCase) >= 0)
                    AppendLog("   （UAC 提权窗口被取消了。改 hosts 必须提权，再点一次并在弹窗里选「是」。）");
                SetStatus("未获得管理员授权", "改 hosts 需要一次管理员确认，点「是」即可", C_Amber);
                return false;
            }
        }

        private string NewJobFile(string kind, string mode, string groups, string source)
        {
            if (!Directory.Exists(AppInfo.LogDir)) Directory.CreateDirectory(AppInfo.LogDir);
            string f = Path.Combine(AppInfo.LogDir, "job_" + DateTime.Now.ToString("yyyyMMdd_HHmmss") + ".txt");
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("kind=" + kind);
            sb.AppendLine("mode=" + mode);
            sb.AppendLine("groups=" + groups);
            sb.AppendLine("source=" + source);
            File.WriteAllText(f, sb.ToString(), new UTF8Encoding(false));
            return f;
        }

        private void BeginJob(string kind, string workerArgs, string main, string sub, bool elevate)
        {
            _busy = true;
            SetBig(false, "正在处理…");
            SetStatus(main, sub, C_Amber);
            _jobKind = kind;
            _progressPath = _jobFile + ".progress";
            _resultPath = _jobFile + ".result";
            try { if (File.Exists(_progressPath)) File.Delete(_progressPath); } catch { }
            try { if (File.Exists(_resultPath)) File.Delete(_resultPath); } catch { }
            _progressLen = 0;
            if (StartWorker(workerArgs, elevate)) _timer.Start();
            else { _busy = false; SetBig(true, "一键加速"); }
        }

        private void Poll()
        {
            if (_progressPath != null && File.Exists(_progressPath))
            {
                try
                {
                    string txt = File.ReadAllText(_progressPath, new UTF8Encoding(false));
                    if (txt.Length > _progressLen)
                    {
                        string add = txt.Substring((int)_progressLen);
                        _progressLen = txt.Length;
                        foreach (string l in add.Replace("\r\n", "\n").TrimEnd('\n').Split('\n'))
                            AppendLog(l);
                        string[] ls = add.Replace("\r\n", "\n").Trim().Split('\n');
                        if (ls.Length > 0)
                        {
                            string last = ls[ls.Length - 1].Trim();
                            if (last.Length > 6) _statusSub.Text = last.Substring(6).Trim();
                        }
                    }
                }
                catch { }
            }
            if (_resultPath != null && File.Exists(_resultPath))
            {
                _timer.Stop();
                Thread.Sleep(150);
                Dictionary<string, string> map = new Dictionary<string, string>();
                try
                {
                    foreach (string l in File.ReadAllLines(_resultPath))
                    {
                        int i = l.IndexOf('=');
                        if (i > 0) map[l.Substring(0, i).Trim()] = l.Substring(i + 1).Trim();
                    }
                }
                catch { }
                string status = map.ContainsKey("status") ? map["status"] : "error";
                string detail = map.ContainsKey("detail") ? map["detail"] : "未知结果";
                string verified = map.ContainsKey("verified") ? map["verified"] : "False";

                if (status == "ok")
                {
                    if (_jobKind == "stop")
                    {
                        SetStatus("已停止加速", detail, C_Grey);
                        SetBig(true, "一键加速");
                        AppendLog("√ " + detail);
                    }
                    else if (_jobKind == "diag")
                    {
                        SetStatus("测速完成", detail, C_Green);
                        SetBig(true, "重新测速并加速");
                        AppendLog("√ " + detail);
                    }
                    else if (_jobKind == "auto")
                    {
                        AppendLog("√ " + detail);
                        SetBig(true, "一键加速");
                        UpdateAutoButton();
                    }
                    else if (_jobKind == "restore")
                    {
                        AppendLog("√ " + detail);
                        SetBig(true, "一键加速");
                    }
                    else
                    {
                        if (verified == "False")
                        {
                            SetStatus("写入可能被安全软件拦了", "请看下方日志", C_Amber);
                            AppendLog("!! 回读校验不通过：hosts 可能被安全软件的防护改回去了。");
                            AppendLog("   处理办法：把 " + AppInfo.Dir + " 加进杀软信任项，或关掉它的 hosts 防护，再加速一次。");
                        }
                        else
                        {
                            SetStatus("已加速 · 生效中", detail, C_Green);
                            AppendLog("√ " + detail);
                        }
                        SetBig(true, "重新测速并加速");
                    }
                }
                else
                {
                    SetStatus("操作失败", detail, C_Red);
                    AppendLog("!! " + detail);
                    SetBig(true, "一键加速");
                }
                _busy = false;
                _jobKind = "";
                if (_jobKind != "diag") { try { RefreshStatus(); } catch { } }
            }
        }

        // ------------------------------------------------------ 动作
        private string GroupCsv()
        {
            List<string> g = new List<string>();
            if (_ckSteam.Checked) g.Add("steam");
            if (_ckGit.Checked) g.Add("github");
            if (_ckAi.Checked) g.Add("ai");
            return string.Join(",", g.ToArray());
        }

        private void StartAccel()
        {
            string groups = GroupCsv();
            if (groups.Length == 0)
            {
                MessageBox.Show(this, "请至少勾选一个加速范围。", AppInfo.Title, MessageBoxButtons.OK, MessageBoxIcon.Information);
                return;
            }
            string mode = _rbFull.Checked ? "full" : (_rbBoth.Checked ? "both" : "direct");
            _jobFile = NewJobFile("accel", mode, groups, "主界面");
            AppendLog("");
            AppendLog("===== 开始加速（模式：" + mode + "，范围：" + groups + "）=====");
            BeginJob("accel", "--job \"" + _jobFile + "\"", "正在测速…",
                     "正在多源 DNS 解析，并做 TCP + TLS 双验证", true);
        }

        private void StopAccel()
        {
            _jobFile = NewJobFile("stop", "direct", "", "主界面");
            AppendLog("");
            AppendLog("===== 停止加速 =====");
            BeginJob("stop", "--stop --job \"" + _jobFile + "\"", "正在停止…",
                     "移除本工具写入的条目（Steam++ 的条目不受影响）", true);
        }

        private void RestoreHosts()
        {
            if (MessageBox.Show(this,
                "将把 hosts 还原成「本程序第一次运行之前」的原始内容。\r\n\r\n" +
                "注意：这会连同 Steam++ 后来写入的条目一起清掉（Steam++ 下次启动会自己重写）。\r\n\r\n确定继续吗？",
                AppInfo.Title, MessageBoxButtons.YesNo, MessageBoxIcon.Warning) != DialogResult.Yes) return;
            _jobFile = NewJobFile("restore", "direct", "", "主界面");
            AppendLog("");
            AppendLog("===== 还原 hosts =====");
            BeginJob("restore", "--restore --job \"" + _jobFile + "\"", "正在还原…", "从原始备份恢复 hosts", true);
        }

        private void Diagnose()
        {
            string groups = GroupCsv();
            if (groups.Length == 0) groups = "steam,github,ai";
            _jobFile = NewJobFile("diag", "direct", groups, "主界面");
            AppendLog("");
            AppendLog("===== 详细测速（只测不改，不动 hosts）=====");
            BeginJob("diag", "--diagnose --job \"" + _jobFile + "\"", "正在测速…",
                     "只测速，不会改动 hosts", false);
        }

        private void ToggleAutostart()
        {
            bool has = _btnAuto.Text.IndexOf("已开") >= 0;
            _jobFile = NewJobFile("auto", "direct", "", "主界面");
            AppendLog("");
            AppendLog(has ? "===== 取消开机自动加速 =====" : "===== 设置开机自动加速 =====");
            BeginJob("auto", (has ? "--remove-auto" : "--install-auto") + " --job \"" + _jobFile + "\"",
                     has ? "正在取消…" : "正在设置…",
                     has ? "删除计划任务" : "创建登录后静默执行的计划任务", true);
        }
    }

    // ========================================================================
    //  入口
    // ========================================================================
    static class Program
    {
        [STAThread]
        static void Main(string[] args)
        {
            bool hasWork = args.Any(delegate(string a)
            {
                return a == "--job" || a == "--stop" || a == "--restore" || a == "--diagnose" ||
                       a == "--preview" ||
                       a == "--install-auto" || a == "--remove-auto" || a == "--auto";
            });
            if (hasWork) { Worker.Run(args); return; }

            if (args.Any(delegate(string a) { return a == "--selftest"; })) { SelfTest(); return; }
            if (args.Any(delegate(string a) { return a == "--render"; }))
            {
                string outPath = null;
                for (int i = 0; i < args.Length - 1; i++) if (args[i] == "--render") outPath = args[i + 1];
                RenderUi(outPath);
                return;
            }

            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            Application.Run(new MainForm());
        }

        // -------------------------------------------------- 自检（不弹任何窗口）
        private static void SelfTest()
        {
            StringBuilder sb = new StringBuilder();
            sb.AppendLine("SteamFast v" + AppInfo.Version + " 自检  " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss"));
            sb.AppendLine("exe     : " + AppInfo.ExePath);
            sb.AppendLine("程序目录: " + AppInfo.Dir);
            sb.AppendLine("hosts   : " + AppInfo.HostsPath);
            sb.AppendLine("管理员  : " + IsAdmin());
            sb.AppendLine("DPI     : " + DpiInfo());
            sb.AppendLine();
            sb.AppendLine("--- 引擎测速 ---");
            List<string> doms = Domains.All();
            List<DomainResult> res = Engine.Run(doms, null);
            int ok = 0, skip = 0;
            foreach (DomainResult r in res.OrderBy(delegate(DomainResult x) { return x.Domain; }))
            {
                if (r.Ip != null) { ok++; sb.AppendLine("OK    " + Worker.Pad(r.Domain, 38) + " -> " + Worker.Pad(r.Ip, 16) + r.Ms + "ms"); }
                else { skip++; sb.AppendLine("SKIP  " + Worker.Pad(r.Domain, 38) + r.Note); }
            }
            sb.AppendLine();
            sb.AppendLine("可用 " + ok + " / 跳过 " + skip + " / 共 " + res.Count);

            sb.AppendLine();
            sb.AppendLine("--- hosts 现状 ---");
            try
            {
                sb.AppendLine("总行数 " + HostsFile.ReadText().Replace("\r\n", "\n").Split('\n').Length);
                sb.AppendLine("已有 SteamFast 区块: " + HostsFile.HasBlock() + "（有效 " + HostsFile.PublishedCount() + " 条）");
                sb.AppendLine("已有 Steam++ 区块: " + HostsFile.HasSppBlock());
            }
            catch (Exception ex) { sb.AppendLine("读取失败 " + ex.Message); }

            sb.AppendLine();
            sb.AppendLine("--- hosts 区块读写测试（副本上做）---");
            string td = Path.Combine(AppInfo.Dir, "_hosts_test");
            try
            {
                if (Directory.Exists(td)) Directory.Delete(td, true);
                Directory.CreateDirectory(td);
                string backupDir = Path.Combine(td, "backup");
                Directory.CreateDirectory(backupDir);

                // 直接对副本跑一遍 Apply/Remove 的等价逻辑
                string fake = Path.Combine(td, "hosts");
                string sample = string.Join("\r\n", new string[] {
                    "# Copyright (c) 1993-2009 Microsoft Corp.", "#", "# sample HOSTS file.", "",
                    SetupSppBlock(), "127.0.0.1 steamcdn-a.akamaihd.net", "127.0.0.1 github.com", "" });
                File.WriteAllText(fake, sample, new UTF8Encoding(false));

                string t1 = BlockApply(fake, new string[] { "185.199.110.133  raw.githubusercontent.com", "20.205.243.166  github.com" });
                int iOur = IndexOfLine(t1, "185.199.110.133  raw.githubusercontent.com");
                int iSpp = IndexOfLine(t1, "127.0.0.1 steamcdn-a.akamaihd.net");
                sb.AppendLine("优先于 Steam++ 条目: " + ((iOur >= 0) && (iOur < iSpp)) + "  （我方第 " + (iOur + 1) + " 行 / Steam++ 第 " + (iSpp + 1) + " 行）");
                sb.AppendLine("Steam++ 条目未被毁 : " + t1.Contains("127.0.0.1 steamcdn-a.akamaihd.net"));
                sb.AppendLine("优选条目已写入     : " + t1.Contains("185.199.110.133"));

                string t2 = BlockApply(fake, new string[] { "1.2.3.4  raw.githubusercontent.com" });
                sb.AppendLine("二次加速不叠加     : " + (CountOf(t2, AppInfo.StartMark) == 1));
                sb.AppendLine("旧条目被替换       : " + ((!t2.Contains("185.199.110.133")) && t2.Contains("1.2.3.4")));

                string t3 = BlockRemove(fake);
                sb.AppendLine("停止后区块已移除   : " + (!t3.Contains(AppInfo.StartMark)));
                sb.AppendLine("停止后 Steam++ 仍在: " + t3.Contains("127.0.0.1 steamcdn-a.akamaihd.net"));
                Directory.Delete(td, true);
            }
            catch (Exception ex) { sb.AppendLine("测试出错: " + ex.Message); }

            string outp = Path.Combine(AppInfo.Dir, "selftest_exe.txt");
            File.WriteAllText(outp, sb.ToString(), new UTF8Encoding(true));
            if (Environment.UserInteractive) { }
        }

        private static string SetupSppBlock() { return AppInfo.SppMark; }

        private static string DpiInfo()
        {
            try
            {
                using (Graphics g = Graphics.FromHwnd(IntPtr.Zero)) return g.DpiX + " dpi (缩放 " + (int)(g.DpiX / 96.0 * 100) + "%)";
            }
            catch { return "未知"; }
        }

        private static bool IsAdmin()
        {
            try
            {
                System.Security.Principal.WindowsIdentity id = System.Security.Principal.WindowsIdentity.GetCurrent();
                return new System.Security.Principal.WindowsPrincipal(id)
                    .IsInRole(System.Security.Principal.WindowsBuiltInRole.Administrator);
            }
            catch { return false; }
        }

        // ---- 副本上的区块逻辑（与 HostsFile 同规则，只是路径可传）----
        private static string BlockApply(string path, string[] entries)
        {
            string text = File.ReadAllText(path);
            List<string> lines = StripBlock(text);
            while (lines.Count > 0 && lines[lines.Count - 1].Trim().Length == 0) lines.RemoveAt(lines.Count - 1);
            List<string> block = new List<string>();
            block.Add(AppInfo.StartMark);
            block.Add("# generated");
            foreach (string e in entries) block.Add(e);
            block.Add(AppInfo.EndMark);
            int insert = lines.Count;
            for (int i = 0; i < lines.Count; i++)
            {
                string s = lines[i].Trim();
                if (s.Length > 0 && !s.StartsWith("#")) { insert = i; break; }
            }
            while (insert > 0) { if (lines[insert - 1].Trim().StartsWith("#")) insert--; else break; }
            lines.InsertRange(insert, block);
            lines.Add("");
            string outp = string.Join("\r\n", lines.ToArray());
            File.WriteAllText(path, outp, new UTF8Encoding(false));
            return outp;
        }

        private static string BlockRemove(string path)
        {
            string text = File.ReadAllText(path);
            List<string> lines = StripBlock(text);
            while (lines.Count > 0 && lines[lines.Count - 1].Trim().Length == 0) lines.RemoveAt(lines.Count - 1);
            lines.Add("");
            string outp = string.Join("\r\n", lines.ToArray());
            File.WriteAllText(path, outp, new UTF8Encoding(false));
            return outp;
        }

        private static List<string> StripBlock(string text)
        {
            List<string> outp = new List<string>();
            bool inB = false;
            foreach (string l in text.Replace("\r\n", "\n").Split('\n'))
            {
                string t = l.Trim();
                if (t == AppInfo.StartMark) { inB = true; continue; }
                if (t == AppInfo.EndMark) { inB = false; continue; }
                if (inB) continue;
                outp.Add(l);
            }
            return outp;
        }

        private static int IndexOfLine(string text, string line)
        {
            string[] ls = text.Replace("\r\n", "\n").Split('\n');
            for (int i = 0; i < ls.Length; i++) if (ls[i] == line) return i;
            return -1;
        }

        private static int CountOf(string text, string m)
        {
            int n = 0, i = 0;
            while ((i = text.IndexOf(m, i, StringComparison.Ordinal)) >= 0) { n++; i += m.Length; }
            return n;
        }

        // -------------------------------------------------- 离屏渲染界面截图（不弹窗、不打扰）
        private static void RenderUi(string outPath)
        {
            if (string.IsNullOrEmpty(outPath)) outPath = Path.Combine(AppInfo.Dir, "ui_preview.png");
            Application.EnableVisualStyles();
            Application.SetCompatibleTextRenderingDefault(false);
            MainForm f = new MainForm();
            f.ShowInTaskbar = false;
            f.StartPosition = FormStartPosition.Manual;
            f.Location = new Point(-32000, -32000);
            f.Opacity = 0.0;
            try
            {
                f.Show();
                Application.DoEvents();
                Thread.Sleep(400);
                Application.DoEvents();
                using (Bitmap bmp = new Bitmap(f.Width, f.Height))
                {
                    f.DrawToBitmap(bmp, new Rectangle(0, 0, f.Width, f.Height));
                    bmp.Save(outPath, ImageFormat.Png);
                }
                File.AppendAllText(Path.Combine(AppInfo.Dir, "ui_render.txt"),
                    f.Width + "x" + f.Height + " -> " + outPath + "  " + DateTime.Now.ToString("HH:mm:ss") + "\r\n");
            }
            catch (Exception ex)
            {
                try { File.AppendAllText(Path.Combine(AppInfo.Dir, "ui_render.txt"), "ERR " + ex.Message + "\r\n"); } catch { }
            }
            finally { try { f.Close(); f.Dispose(); } catch { } }
        }
    }
}
