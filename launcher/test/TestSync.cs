// The launcher's update path, end to end, with no window: Release.cs, Sync.cs
// and LocalServer.cs against releases client/publish.py signed
// (make_fixture.py), served by a small web server in this process.
//
//   powershell -ExecutionPolicy Bypass -File launcher\test\run.ps1
//
// What a player's launcher does on a start is what Run() below does: a Sync
// over a game folder, settled, then looked at. Nothing here opens a window or
// starts the projector.
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

static class TestSync
{
    static int fails, oks;
    static string W;
    static StaticServer web;
    static KeySet resource, launcher;

    static void Check(string label, object got, object want)
    {
        bool ok = Equals(got, want);
        if (ok) { oks++; Console.WriteLine("  ok  " + label); }
        else
        {
            fails++;
            Console.WriteLine("FAIL  " + label + "\n   got  " + got + "\n   want " + want);
        }
    }

    static int Main(string[] args)
    {
        if (args.Length > 0 && args[0] == "install") return Install(args);
        W = Path.GetFullPath(args[0]);
        string logs = Path.Combine(W, "log");
        Directory.CreateDirectory(logs);
        Environment.SetEnvironmentVariable("LAVA_LOG_DIR", logs);
        resource = Keys("resource");
        launcher = Keys("launcher");
        web = new StaticServer();
        web.Start();
        try { Run(); }
        catch (Exception e)
        {
            fails++;
            Console.WriteLine("FAIL  crashed: " + e);
        }
        finally { web.Stop(); }
        Console.WriteLine();
        Console.WriteLine(fails == 0 ? "launcher sync OK (" + oks + " checks)" : "FAILED " + fails + " of " + (fails + oks));
        return fails == 0 ? 0 : 1;
    }

    // A real install, timed, with progress on the console:
    //   TestSync.exe install <root url> <resource.keys> <launcher.keys> <game dir> [--verify]
    // What the launcher's window would show, without the window.
    static int Install(string[] a)
    {
        Sync s = new Sync(a[4], a[1], new KeySet(File.ReadAllLines(a[2])), new KeySet(File.ReadAllLines(a[3])), 999, null);
        s.FullVerify = a.Length > 5 && a[5] == "--verify";
        DateTime t0 = DateTime.UtcNow;
        s.Start();
        while (!s.Wait(5000))
        {
            long d, tot;
            int f, ft;
            s.Progress(out d, out tot, out f, out ft);
            Console.WriteLine("  {0,5:0}s  {1,-11} {2,7:0.0} / {3,7:0.0} MB  {4}/{5} files  {6}",
                (DateTime.UtcNow - t0).TotalSeconds, s.State, d / 1048576.0, tot / 1048576.0, f, ft, s.Note);
        }
        Console.WriteLine("{0}: {1} after {2:0.0}s", s.State, s.Note, (DateTime.UtcNow - t0).TotalSeconds);
        return s.Playable ? 0 : 1;
    }

    static KeySet Keys(string name)
    {
        return new KeySet(File.ReadAllLines(Path.Combine(W, "keys", name + ".keys")));
    }

    static string Served(string name) { return Path.Combine(W, "served", name); }

    static string Fresh(string name)
    {
        string d = Path.Combine(W, "games", name);
        if (Directory.Exists(d)) Directory.Delete(d, true);
        Directory.CreateDirectory(d);
        return d;
    }

    static Sync Start(string game, int version, string exe, bool verify)
    {
        Sync s = new Sync(game, web.Url + "download/client/", resource, launcher, version, exe);
        s.FullVerify = verify;
        web.StoreHits = 0;
        s.Start();
        if (!s.Wait(120000)) throw new Exception("sync did not settle");
        return s;
    }

    static byte[] Expect(string version, string path)
    {
        return File.ReadAllBytes(Path.Combine(W, "expect", version, path.Replace('/', '\\')));
    }

    static bool SameFiles(string game, string version)
    {
        string root = Path.Combine(W, "expect", version);
        foreach (string f in Directory.GetFiles(root, "*", SearchOption.AllDirectories))
        {
            string rel = f.Substring(root.Length + 1);
            string mine = Path.Combine(game, "res", rel);
            if (!File.Exists(mine) || !Same(File.ReadAllBytes(mine), File.ReadAllBytes(f)))
            {
                Console.WriteLine("      differs: " + rel);
                return false;
            }
        }
        return true;
    }

    static bool Same(byte[] a, byte[] b)
    {
        if (a == null || b == null || a.Length != b.Length) return false;
        for (int i = 0; i < a.Length; i++) if (a[i] != b[i]) return false;
        return true;
    }

    static void Run()
    {
        // --- a fresh install ----------------------------------------------------
        string game = Fresh("main");
        web.Root = Served("r1");
        Sync s = Start(game, 99, null, false);
        Check("install: ready", s.State, SyncState.Ready);
        Check("install: every file is release 1's", SameFiles(game, "v1"), true);
        Check("install: two paths, one blob, one download", web.StoreHits, 7);
        Check("install: the accepted pointer is kept", File.Exists(Path.Combine(game, ".lava", "current.txt")), true);
        Check("install: the index is written", File.Exists(Path.Combine(game, ".lava", "index.tsv")), true);
        Check("install: staging is empty", Directory.GetFiles(Path.Combine(game, ".lava", "staging")).Length, 0);

        // --- the next start ----------------------------------------------------------
        s = Start(game, 99, null, false);
        Check("restart: ready", s.State, SyncState.Ready);
        Check("restart: nothing downloaded", web.StoreHits, 0);
        Check("restart: says it is up to date", s.Note, "Игра в актуальном состоянии");

        // --- a file changed on the disk -------------------------------------------------
        string mainSwf = Path.Combine(game, "res", "main.swf");
        byte[] wrong = Expect("v1", "main.swf");
        wrong = (byte[])wrong.Clone();
        wrong[wrong.Length - 1] ^= 0xFF;
        File.WriteAllBytes(mainSwf, wrong);
        s = Start(game, 99, null, false);
        Check("tampered: ready again", s.State, SyncState.Ready);
        Check("tampered: the file is release 1's again", Same(File.ReadAllBytes(mainSwf), Expect("v1", "main.swf")), true);
        Check("tampered: one download", web.StoreHits, 1);
        // Who changed it is not knowable -- a disk fault or the player's own
        // patch look the same -- so the changed copy is kept, not destroyed.
        Check("tampered: the changed copy is kept aside",
              Directory.GetFiles(Path.Combine(game, ".lava", "replaced"), "main.swf", SearchOption.AllDirectories).Length, 1);

        // --- the same, with the time put back: the index vouches, --verify does not -----------
        DateTime t = File.GetLastWriteTimeUtc(mainSwf);
        File.WriteAllBytes(mainSwf, wrong);
        File.SetLastWriteTimeUtc(mainSwf, t);
        s = Start(game, 99, null, false);
        Check("same size and time: the index is trusted at start", web.StoreHits, 0);
        s = Start(game, 99, null, true);
        Check("--verify: the file is hashed and fetched again", web.StoreHits, 1);
        Check("--verify: release 1's bytes", Same(File.ReadAllBytes(mainSwf), Expect("v1", "main.swf")), true);

        // --- a file the launcher never vouched for --------------------------------------------
        File.Delete(Path.Combine(game, ".lava", "index.tsv"));
        string loc = Path.Combine(game, "res", "database", "locations.xml");
        File.WriteAllText(loc, "the player's own map names");
        s = Start(game, 99, null, false);
        Check("unknown file: ready", s.State, SyncState.Ready);
        Check("unknown file: release 1's put in its place", Same(File.ReadAllBytes(loc), Expect("v1", "database/locations.xml")), true);
        string[] aside = Directory.Exists(Path.Combine(game, ".lava", "replaced"))
            ? Directory.GetFiles(Path.Combine(game, ".lava", "replaced"), "locations.xml", SearchOption.AllDirectories)
            : new string[0];
        Check("unknown file: the player's copy is kept aside", aside.Length == 1 && File.ReadAllText(aside[0]) == "the player's own map names", true);

        // --- release 2 -----------------------------------------------------------------------
        web.Root = Served("r2");
        s = Start(game, 99, null, false);
        Check("update: ready", s.State, SyncState.Ready);
        Check("update: every file is release 2's", SameFiles(game, "v2"), true);
        Check("update: only the changed and added files downloaded", web.StoreHits, 3);
        Check("update: says how many files changed", s.Note, "Игра обновлена: 3 файла");

        // --- the game's web server -------------------------------------------------------------
        LocalServer ls = new LocalServer(s, null, "127.0.0.1", 9775);
        ls.Start();
        string at = "http://127.0.0.1:" + ls.Port + "/res/";
        Check("serve: a release file", Same(Get(at + "main.swf"), Expect("v2", "main.swf")), true);
        Check("serve: any case of its name", Same(Get(at + "MAIN.SWF"), Expect("v2", "main.swf")), true);
        Check("serve: a name with a space", Same(Get(at + "locations/libs/Abu%20Hamad.swf"), Expect("v2", "locations/libs/Abu Hamad.swf")), true);
        Check("serve: a file release 2 dropped is not served, though it is on the disk",
              Get(at + "mobs/old.swf") == null && File.Exists(Path.Combine(game, "res", "mobs", "old.swf")), true);
        Check("serve: nothing outside the release", Get(at + "../.lava/current.txt"), null);
        byte[] cs = Get(at + "xmldocs/csettings_v1.xml");
        Check("serve: csettings is made up on the spot", cs != null && Encoding.UTF8.GetString(cs).Contains("<resource base="), true);
        string snd = Path.Combine(game, "res", "sounds", "new.swf");
        File.WriteAllText(snd, "changed while the game runs");
        web.StoreHits = 0;
        Check("serve: a file changed after the check is served as the release has it",
              Same(Get(at + "sounds/new.swf"), Expect("v2", "sounds/new.swf")), true);
        Check("serve: and mended on the disk", Same(File.ReadAllBytes(snd), Expect("v2", "sounds/new.swf")), true);
        Check("serve: from the store", web.StoreHits, 1);
        Check("serve: a request naming another host is refused (DNS rebinding)",
              StatusLine(ls.Port, "/exe/lavaclient/loaduser/?ajax", "evil.example:" + ls.Port), "HTTP/1.1 403 Forbidden");
        Check("serve: the same request naming this machine is answered",
              StatusLine(ls.Port, "/exe/lavaclient/loaduser/?ajax", "127.0.0.1:" + ls.Port), "HTTP/1.1 200 OK");
        ls.Stop();

        // --- what is refused -------------------------------------------------------------------
        web.Root = Served("stranger");
        s = Start(game, 99, null, false);
        Check("stranger's pointer: not taken, the installed release plays", s.State, SyncState.Offline);
        Check("stranger's pointer: the note says why", s.Note.Contains("подписи"), true);
        Check("stranger's pointer: nothing downloaded", web.StoreHits, 0);

        web.Root = Served("r1again");
        s = Start(game, 99, null, false);
        Check("an older release after a newer one: not taken", s.State, SyncState.Offline);
        Check("an older release: the files stay release 2's", SameFiles(game, "v2"), true);

        web.Root = null;
        s = Start(game, 99, null, false);
        Check("no server: the installed release plays", s.State, SyncState.Offline);

        string fresh = Fresh("nothing");
        s = Start(fresh, 99, null, false);
        Check("no server and nothing installed: cannot play", s.State, SyncState.Failed);

        string g2 = Fresh("badblob");
        web.Root = Served("r1");
        Start(g2, 99, null, false);
        web.Root = Served("badblob");
        s = Start(g2, 99, null, false);
        Check("a store file that is not what the release says: the installed release plays", s.State, SyncState.Offline);
        Check("a store file that is not what the release says: nothing half-applied", SameFiles(g2, "v1"), true);
        string g5 = Fresh("badblob-fresh");
        s = Start(g5, 99, null, false);
        Check("a store file that is not what the release says, nothing installed: failed", s.State, SyncState.Failed);

        // --- a new launcher ----------------------------------------------------------------------
        string g3 = Fresh("selfupdate");
        string exe = Path.Combine(g3, "LavaReborn.exe");
        File.WriteAllText(exe, "MZ launcher build 1");
        web.Root = Served("r2");
        s = Start(g3, 1, exe, false);
        Check("new launcher: restart asked", s.State, SyncState.Restarting);
        Check("new launcher: version", s.NewVersion, 2);
        Check("new launcher: in place under the old name", File.ReadAllText(exe), "MZ launcher build 2");
        Check("new launcher: the old one stepped aside", File.ReadAllText(exe + ".old"), "MZ launcher build 1");
        Sync.CleanOld(exe);
        Check("new launcher: the next start clears the old one", File.Exists(exe + ".old"), false);
        s = Start(g3, 2, exe, false);
        Check("new launcher: running it, the game installs", s.State, SyncState.Ready);

        string g4 = Fresh("badexe");
        string exe4 = Path.Combine(g4, "LavaReborn.exe");
        File.WriteAllText(exe4, "MZ launcher build 1");
        web.Root = Served("badexe");
        s = Start(g4, 1, exe4, false);
        Check("a launcher signed by a stranger: refused, sent to the site", s.State, SyncState.MustUpdate);
        Check("a launcher signed by a stranger: the exe is untouched", File.ReadAllText(exe4), "MZ launcher build 1");
        Check("a launcher signed by a stranger: nothing left beside it",
              File.Exists(exe4 + ".new") || File.Exists(exe4 + ".old"), false);

        // --- the documents themselves ------------------------------------------------------------
        byte[] doc = File.ReadAllBytes(Path.Combine(Served("r2"), "current.txt"));
        Pointer p = Pointer.Read(resource, doc);
        Check("pointer: the one publish.py signed reads back", p.LauncherVersion, 2);
        byte[] bent = (byte[])doc.Clone();
        bent[20] ^= 1;
        bool refused = false;
        try { Pointer.Read(resource, bent); }
        catch (ReleaseException) { refused = true; }
        Check("pointer: one bit changed is refused", refused, true);
        Check("manifest: a '..' path is refused", Manifest.PathOk("a/../b"), false);
        Check("manifest: a part ending in a dot is refused", Manifest.PathOk("a./b"), false);
        Check("manifest: .lava is the launcher's own", Manifest.PathOk(".LAVA/x"), false);
        Check("manifest: a space inside a name is fine", Manifest.PathOk("locations/libs/Abu Hamad.swf"), true);
        Check("manifest: a device name is refused", Manifest.PathOk("mobs/CON.swf"), false);
        Check("manifest: a name merely starting like one is fine", Manifest.PathOk("console.swf"), true);
        Check("manifest: a character Windows refuses is refused", Manifest.PathOk("a/b?c"), false);
        Check("manifest: a letter outside ASCII is refused", Manifest.PathOk("mobs/б.swf"), false);
        Check("manifest: a path over 150 characters is refused", Manifest.PathOk(new string('a', 151)), false);
    }

    // The first line of the answer to a GET with a Host of our choosing,
    // which HttpWebRequest will not send.
    static string StatusLine(int port, string path, string host)
    {
        using (TcpClient c = new TcpClient("127.0.0.1", port))
        using (NetworkStream s = c.GetStream())
        {
            byte[] rq = Encoding.ASCII.GetBytes("GET " + path + " HTTP/1.1\r\nHost: " + host + "\r\nConnection: close\r\n\r\n");
            s.Write(rq, 0, rq.Length);
            StringBuilder sb = new StringBuilder();
            int ch;
            while ((ch = s.ReadByte()) >= 0 && ch != '\n') sb.Append((char)ch);
            return sb.ToString().TrimEnd('\r');
        }
    }

    static byte[] Get(string url)
    {
        try
        {
            HttpWebRequest rq = (HttpWebRequest)WebRequest.Create(url);
            rq.Timeout = 30000;
            using (WebResponse rs = rq.GetResponse())
            using (Stream st = rs.GetResponseStream())
            using (MemoryStream m = new MemoryStream())
            {
                st.CopyTo(m);
                return m.ToArray();
            }
        }
        catch (WebException) { return null; }
    }
}

// Files under Root at /download/client/, nothing else. Root null: every
// request is a 404, the server being down as far as a launcher can tell.
class StaticServer
{
    TcpListener listener;
    volatile bool running;
    public volatile string Root;
    public int Port;
    public int StoreHits;

    public string Url { get { return "http://127.0.0.1:" + Port + "/"; } }

    public void Start()
    {
        listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        Port = ((IPEndPoint)listener.LocalEndpoint).Port;
        running = true;
        Thread t = new Thread(delegate ()
        {
            while (running)
            {
                TcpClient c;
                try { c = listener.AcceptTcpClient(); }
                catch { return; }
                ThreadPool.QueueUserWorkItem(Serve, c);
            }
        });
        t.IsBackground = true;
        t.Start();
    }

    public void Stop()
    {
        running = false;
        try { listener.Stop(); } catch { }
    }

    void Serve(object o)
    {
        TcpClient c = (TcpClient)o;
        try
        {
            using (NetworkStream s = c.GetStream())
            {
                string line = ReadLine(s);
                while (true) { string h = ReadLine(s); if (h == null || h.Length == 0) break; }
                if (line == null) return;
                string target = line.Split(' ')[1];
                int q = target.IndexOf('?');
                if (q >= 0) target = target.Substring(0, q);
                target = Uri.UnescapeDataString(target);
                string root = Root;
                byte[] body = null;
                const string PREFIX = "/download/client/";
                if (root != null && target.StartsWith(PREFIX) && target.IndexOf("..") < 0)
                {
                    string rel = target.Substring(PREFIX.Length);
                    string f = Path.Combine(root, rel.Replace('/', '\\'));
                    if (File.Exists(f))
                    {
                        body = File.ReadAllBytes(f);
                        if (rel.StartsWith("store/")) Interlocked.Increment(ref StoreHits);
                    }
                }
                string head = body != null
                    ? "HTTP/1.1 200 OK\r\nContent-Type: application/octet-stream\r\nContent-Length: " + body.Length + "\r\nConnection: close\r\n\r\n"
                    : "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n";
                byte[] hb = Encoding.ASCII.GetBytes(head);
                s.Write(hb, 0, hb.Length);
                if (body != null) s.Write(body, 0, body.Length);
                s.Flush();
            }
        }
        catch { }
        finally { try { c.Close(); } catch { } }
    }

    static string ReadLine(Stream s)
    {
        StringBuilder sb = new StringBuilder();
        while (true)
        {
            int ch = s.ReadByte();
            if (ch < 0) return sb.Length == 0 ? null : sb.ToString();
            if (ch == '\n') return sb.ToString().TrimEnd('\r');
            sb.Append((char)ch);
        }
    }
}
