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
        Check("restart: no files put in place, nothing for the panel to count", s.Updated, 0);
        Check("restart: the release's commit, from its manifest", s.Current.Source, new string('1', 40));

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
        Check("update: the panel's count", Versions.Updated(s.Updated), "Игра обновлена: 3 файла");
        Check("update: the release's commit is release 2's", s.Current.Source, new string('2', 40));
        Pointer r2p = Pointer.Read(resource, File.ReadAllBytes(Path.Combine(Served("r2"), "current.txt")));
        Check("update: the pointer it came with is kept beside it",
              s.Accepted != null && s.Accepted.Serial == r2p.Serial && s.Accepted.Created == r2p.Created, true);

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

        // The client's goodbye (tools/widescreen.py, patch 10): a form posted
        // as the patched main.swf posts it, UTF-8 percent-encoded.
        Goodbye heard = null;
        ls.Bye += delegate(Goodbye g) { heard = g; };
        string form = "why=kick&admin=Lava%20Reborn&seconds=0&reason=" +
                      Uri.EscapeDataString("Пароль аккаунта сменён.");
        Check("bye: answered", Post("http://127.0.0.1:" + ls.Port + "/exe/lavaclient/bye", form), "ok=1");
        Check("bye: heard as a kick, with who and why",
              heard != null ? heard.Why + "|" + heard.Admin + "|" + heard.Seconds + "|" + heard.Reason : null,
              "kick|Lava Reborn|0|Пароль аккаунта сменён.");
        Check("bye: a client sending its code page is read too (cp1251)",
              Goodbye.Parse(Encoding.ASCII.GetBytes("why=kick&reason=%CF%E0%F0%EE%EB%FC")).Reason, "Пароль");
        Check("bye: anything but a kick is a lost connection",
              Goodbye.Parse(Encoding.ASCII.GetBytes("why=whatever")).Why, "lost");
        ls.Stop();

        // --- what is refused -------------------------------------------------------------------
        web.Root = Served("stranger");
        s = Start(game, 99, null, false);
        Check("stranger's pointer: not taken, the installed release plays", s.State, SyncState.Offline);
        Check("stranger's pointer: the note says why", s.Note.Contains("подписи"), true);
        Check("stranger's pointer: named as refused", s.Cause, OfflineCause.Refused);
        Check("stranger's pointer: nothing downloaded", web.StoreHits, 0);
        Check("stranger's pointer: the release in place is still named by its own pointer",
              s.Accepted != null && s.Accepted.Serial == r2p.Serial, true);

        web.Root = Served("r1again");
        s = Start(game, 99, null, false);
        Check("an older release after a newer one: not taken", s.State, SyncState.Offline);
        Check("an older release: the files stay release 2's", SameFiles(game, "v2"), true);
        Check("an older release: named as refused", s.Cause, OfflineCause.Refused);

        web.Root = null;
        s = Start(game, 99, null, false);
        Check("no server: the installed release plays", s.State, SyncState.Offline);
        Check("no server: named as unreachable", s.Cause, OfflineCause.Unreachable);

        string fresh = Fresh("nothing");
        s = Start(fresh, 99, null, false);
        Check("no server and nothing installed: cannot play", s.State, SyncState.Failed);
        Check("no server and nothing installed: named as the network", s.Failure, SyncFailure.Network);

        string g2 = Fresh("badblob");
        web.Root = Served("r1");
        Start(g2, 99, null, false);
        web.Root = Served("badblob");
        s = Start(g2, 99, null, false);
        Check("a store file that is not what the release says: the installed release plays", s.State, SyncState.Offline);
        Check("a store file that is not what the release says: nothing half-applied", SameFiles(g2, "v1"), true);
        Check("a store file that is not what the release says: named as a failed download", s.Cause, OfflineCause.Download);
        string g5 = Fresh("badblob-fresh");
        s = Start(g5, 99, null, false);
        Check("a store file that is not what the release says, nothing installed: failed", s.State, SyncState.Failed);
        Check("a store file that is not what the release says: named as corrupt", s.Failure, SyncFailure.Corrupt);
        s = Start(Fresh("nothing-kind"), 99, null, false);
        web.Root = Served("r1");

        // --- asking before a first install (the window's "Начать загрузку") -------------------
        string g6 = Fresh("ask");
        s = new Sync(g6, web.Url + "download/client/", resource, launcher, 99, null);
        s.AskFirst = true;
        web.StoreHits = 0;
        s.Start();
        if (!s.Wait(120000)) throw new Exception("sync did not settle");
        Check("ask first: stops at setup", s.State, SyncState.Setup);
        Check("ask first: nothing downloaded", web.StoreHits, 0);
        Check("ask first: it is an install", s.Fresh, true);
        Check("ask first: the size is known", s.NeedBytes > 0, true);
        s.Begin();
        Thread.Sleep(50);
        if (!s.Wait(120000)) throw new Exception("sync did not settle");
        Check("ask first, begun: ready", s.State, SyncState.Ready);
        Check("ask first, begun: release 1's files", SameFiles(g6, "v1"), true);
        s = new Sync(g6, web.Url + "download/client/", resource, launcher, 99, null);
        s.AskFirst = true;
        s.Start();
        s.Wait(120000);
        Check("ask first, installed: no question the next time", s.State, SyncState.Ready);

        // --- a pause the moment the download starts, and going on --------------------------------
        string g7 = Fresh("pause");
        Sync ps = new Sync(g7, web.Url + "download/client/", resource, launcher, 99, null);
        ps.Changed = delegate { if (ps.State == SyncState.Downloading) ps.Pause(); };
        web.StoreHits = 0;
        ps.Start();
        if (!ps.Wait(120000)) throw new Exception("sync did not settle");
        Check("pause: paused", ps.State, SyncState.Paused);
        Check("pause: not playable", ps.Playable, false);
        ps.Changed = null;
        ps.Start();
        Thread.Sleep(50);
        if (!ps.Wait(120000)) throw new Exception("sync did not settle");
        Check("pause, going on: ready", ps.State, SyncState.Ready);
        Check("pause, going on: release 1's files", SameFiles(g7, "v1"), true);

        // --- held before anything is fetched (the window moving the folder) ----------------------
        string g8 = Fresh("hold");
        Sync hs = new Sync(g8, web.Url + "download/client/", resource, launcher, 99, null);
        web.StoreHits = 0;
        hs.Start();
        hs.Hold();
        if (!hs.Wait(120000)) throw new Exception("sync did not settle");
        Check("hold: stops before the download", hs.State, SyncState.Paused);
        Check("hold: nothing downloaded", web.StoreHits, 0);

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
        Check("pointer: created is read as publish.py wrote it", Versions.Created(p.Created) != null, true);

        Looks();
        Labels();
        Watches();
    }

    // --- a look at the pointer between runs (Sync.Peek) ---------------------------------------
    static void Looks()
    {
        long serial;
        long r1 = Pointer.Read(resource, File.ReadAllBytes(Path.Combine(Served("r1"), "current.txt"))).Serial;
        long r2 = Pointer.Read(resource, File.ReadAllBytes(Path.Combine(Served("r2"), "current.txt"))).Serial;

        string game = Fresh("peek");
        Sync s = new Sync(game, web.Url + "download/client/", resource, launcher, 99, null);
        web.Root = Served("r2");
        Check("peek: before any run there is nothing to compare with", s.Peek(5000, false, out serial), Peeked.Unknown);
        Check("peek: nor for ИГРАТЬ", s.Peek(5000, true, out serial), Peeked.Unknown);

        web.Root = Served("r1");
        s.Start();
        if (!s.Wait(120000)) throw new Exception("sync did not settle");
        Check("peek: release 1 in place", s.State, SyncState.Ready);
        web.StoreHits = 0;
        Check("peek: the same release published, nothing newer", s.Peek(5000, false, out serial), Peeked.Current);
        Check("peek: its serial", serial, r1);
        Check("peek: nothing is downloaded by a look", web.StoreHits, 0);

        web.Root = Served("r2");
        Check("peek: release 2 published, newer", s.Peek(5000, false, out serial), Peeked.Newer);
        Check("peek: release 2's serial", serial, r2);
        Check("peek: release 2 published, newer for ИГРАТЬ too", s.Peek(5000, true, out serial), Peeked.Newer);
        Check("peek: the look took nothing, release 1's files stay", SameFiles(game, "v1"), true);

        // Release 2's own body, signed by a key the launcher does not know:
        // newer by its serial, and never trusted for it.
        web.Root = Served("stranger");
        Check("peek: a forged pointer is not newer", s.Peek(5000, false, out serial), Peeked.Unknown);
        Check("peek: and has no serial", serial, 0L);

        web.Root = null;
        Check("peek: no server, nothing to go on", s.Peek(5000, false, out serial), Peeked.Unknown);

        web.Silent = true;
        DateTime t0 = DateTime.UtcNow;
        Peeked silent = s.Peek(700, false, out serial);
        double took = (DateTime.UtcNow - t0).TotalMilliseconds;
        web.Silent = false;
        Check("peek: a server that never answers, nothing to go on", silent, Peeked.Unknown);
        Check("peek: and the look gives up in its time (" + (int)took + " ms)", took < 2500, true);

        // A run looks for itself: a look during one says so at once.
        web.Root = Served("r2");
        Peeked during = Peeked.Unknown;
        s.Changed = delegate
        {
            long ignored;
            if (s.State == SyncState.Checking && during == Peeked.Unknown) during = s.Peek(5000, false, out ignored);
        };
        s.Start();
        if (!s.Wait(120000)) throw new Exception("sync did not settle");
        s.Changed = null;
        Check("peek: during a run, busy", during, Peeked.Busy);
        Check("peek: the run took release 2", SameFiles(game, "v2"), true);
        Check("peek: release 2 in place, nothing newer", s.Peek(5000, false, out serial), Peeked.Current);
        Check("peek: release 2 in place, nothing newer for ИГРАТЬ", s.Peek(5000, true, out serial), Peeked.Current);
        web.Root = Served("r1again");
        Check("peek: an older pointer is not newer", s.Peek(5000, false, out serial), Peeked.Current);
        Check("peek: an older pointer is not newer for ИГРАТЬ", s.Peek(5000, true, out serial), Peeked.Current);

        // A release a run was offered and could not download: the watch
        // does not fetch it again (it would every 15 s), "ИГРАТЬ" does, once
        // a press, before the game starts on the release before it.
        string g3 = Fresh("peek-dl");
        web.Root = Served("r1");
        Sync d = Start(g3, 99, null, false);
        web.Root = Served("badblob");
        d.Start();
        if (!d.Wait(120000)) throw new Exception("sync did not settle");
        Check("peek: a release that would not download, release 1 plays",
              d.State == SyncState.Offline && d.Cause == OfflineCause.Download, true);
        Check("peek: to the watch that release is not newer", d.Peek(5000, false, out serial), Peeked.Current);
        Check("peek: to ИГРАТЬ it is, and is tried again", d.Peek(5000, true, out serial), Peeked.Newer);
        Check("peek: the serial tried again is release 2's", serial, r2);
        Check("peek: the release in place is still named release 1",
              d.Accepted != null && d.Accepted.Serial == r1, true);
        web.Root = Served("r2");
        d.Start();
        if (!d.Wait(120000)) throw new Exception("sync did not settle");
        Check("peek: tried again with the store whole, release 2 in place",
              d.State == SyncState.Ready && SameFiles(g3, "v2"), true);
        Check("peek: then nothing newer for ИГРАТЬ", d.Peek(5000, true, out serial), Peeked.Current);

        // The release in place is named from the start of a run, whether or
        // not the run gets as far as Ready: here it is held short of release 2.
        string g4 = Fresh("peek-held");
        web.Root = Served("r1");
        Start(g4, 99, null, false);
        web.Root = Served("r2");
        Sync h = new Sync(g4, web.Url + "download/client/", resource, launcher, 99, null);
        Check("in place: nothing named before a run has read the folder", h.Accepted == null && h.AcceptedSource == null, true);
        h.Start();
        h.Hold();
        if (!h.Wait(120000)) throw new Exception("sync did not settle");
        Check("in place: a run held short of release 2", h.State, SyncState.Paused);
        Check("in place: release 1 is named, from .lava", h.Accepted != null && h.Accepted.Serial == r1, true);
        Check("in place: with its commit", h.AcceptedSource, new string('1', 40));
        Check("in place: and nothing is served from it", h.Current == null, true);

        // A release a run has been through and could not take -- here a new
        // launcher signed by a stranger -- does not call the window back: a
        // launcher unable to replace itself would fetch itself on every look.
        string g2 = Fresh("peek-ln");
        web.Root = Served("r1");
        Start(g2, 99, null, false);
        string exe = Path.Combine(g2, "LavaReborn.exe");
        File.WriteAllText(exe, "MZ launcher build 1");
        web.Root = Served("badexe");
        Sync b = Start(g2, 1, exe, false);
        Check("peek: a launcher that could not be put in place, release 1 plays", b.State, SyncState.Offline);
        Check("peek: that release is not newer to the next look", b.Peek(5000, false, out serial), Peeked.Current);
        Check("peek: nor to ИГРАТЬ, which would fetch the launcher again", b.Peek(5000, true, out serial), Peeked.Current);
        Check("peek: a fresh launcher on the same folder knows nothing yet", new Sync(g2, web.Url + "download/client/",
              resource, launcher, 1, exe).Peek(5000, false, out serial), Peeked.Unknown);
        web.Root = Served("r1");

        Check("newer: a larger serial", Sync.Newer(1791658979, 1791658900), true);
        Check("newer: the same serial", Sync.Newer(1791658979, 1791658979), false);
        Check("newer: a smaller serial", Sync.Newer(1791658900, 1791658979), false);
        Check("newer: nothing known, nothing newer", Sync.Newer(1791658979, 0), false);
    }

    // --- what the window says about versions (Versions) ----------------------------------------
    static void Labels()
    {
        string sha = "b1042e7c0ffee00000000000000000000000000a";
        // 19:02:59 UTC is 22:02 in Moscow, the deploy of 2026-10-10.
        Check("label: the window's tag", Versions.Window(5, "2026-10-10T19:02:59Z", sha),
              "Лаунчер v5 · игра от 10.10 22:02 (b1042e7)");
        Check("label: the settings' line, with the year and the zone", Versions.Game("2026-10-10T19:02:59Z", sha, true),
              "от 10.10.2026 22:02 мск (b1042e7)");
        Check("label: past midnight in Moscow, the next day", Versions.Game("2026-12-31T21:30:00Z", sha, false),
              "от 01.01 00:30 (b1042e7)");
        Check("label: no release yet, the launcher alone", Versions.Window(5, null, null), "Лаунчер v5");
        Check("label: a time that cannot be read is left out", Versions.Window(5, "yesterday", sha),
              "Лаунчер v5 · игра (b1042e7)");
        Check("label: a source that is not a commit is left out", Versions.Window(5, "2026-10-10T19:02:59Z", "unknown"),
              "Лаунчер v5 · игра от 10.10 22:02");
        Check("label: created as UTC", Versions.Created("2026-10-10T19:02:59Z"),
              (DateTime?)new DateTime(2026, 10, 10, 19, 2, 59, DateTimeKind.Utc));
        Check("label: created without its Z is not read", Versions.Created("2026-10-10T19:02:59"), null);
        Check("label: a commit is shortened", Versions.Commit(sha), "b1042e7");
        Check("label: too short for a commit", Versions.Commit("b1042e"), null);
        Check("updated: nothing put in place, nothing said", Versions.Updated(0), "");
        Check("updated: one", Versions.Updated(1), "Игра обновлена: 1 файл");
        Check("updated: three", Versions.Updated(3), "Игра обновлена: 3 файла");
        Check("updated: eleven", Versions.Updated(11), "Игра обновлена: 11 файлов");
        Check("updated: twenty-two", Versions.Updated(22), "Игра обновлена: 22 файла");
        Check("updated: thousands apart", Versions.Updated(29836), "Игра обновлена: 29 836 файлов");
    }

    // --- when the window looks on its own (Watch) ----------------------------------------------
    static void Watches()
    {
        Watch w = new Watch();
        Check("watch: off until armed", w.Due(0) || w.On, false);

        // The window ticks it each second: a look every 15 s for 5 minutes.
        int t0 = 1000, looks = 0, last = 0;
        w.Arm(t0);
        Check("watch: not at once", w.Due(t0), false);
        Check("watch: not before 15 s", w.Due(t0 + 14999), false);
        for (int t = t0 + 1000; t <= t0 + 400000; t += 1000)
            if (w.Due(t)) { looks++; last = t - t0; }
        Check("watch: twenty looks", looks, 20);
        Check("watch: the last at five minutes", last, 300000);
        Check("watch: then it stops itself", w.On, false);

        w.Arm(t0);
        Check("watch: armed again", w.Due(t0 + 15000), true);
        w.Stop();
        Check("watch: stopped, no look", w.Due(t0 + 30000), false);
        Check("watch: stopped is off", w.On, false);

        // Environment.TickCount wraps after 24.9 days of uptime.
        int edge = int.MaxValue - 5000;
        w.Arm(edge);
        Check("watch: across the wrap", w.Due(unchecked(edge + 15000)), true);
        Check("watch: across the wrap, not twice", w.Due(unchecked(edge + 16000)), false);
        Check("watch: across the wrap, to the end", w.Due(unchecked(edge + 300001)), false);
        Check("watch: across the wrap, then off", w.On, false);

        // What a newer release found by a look leads to.
        foreach (SyncState st in Enum.GetValues(typeof(SyncState)))
        {
            Check("act: game running, " + st + ": only told, never taken", Watch.Decide(true, true, st), Watch.Act.Tell);
            Check("act: game starting, " + st + ": nothing", Watch.Decide(false, true, st), Watch.Act.Nothing);
            Check("act: game closed, " + st, Watch.Decide(false, false, st),
                  st == SyncState.Ready || st == SyncState.Offline ? Watch.Act.Take : Watch.Act.Nothing);
        }
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

    static string Post(string url, string form)
    {
        try
        {
            HttpWebRequest rq = (HttpWebRequest)WebRequest.Create(url);
            rq.Method = "POST";
            rq.ContentType = "application/x-www-form-urlencoded";
            rq.Timeout = 30000;
            byte[] b = Encoding.ASCII.GetBytes(form);
            using (Stream st = rq.GetRequestStream()) st.Write(b, 0, b.Length);
            using (WebResponse rs = rq.GetResponse())
            using (StreamReader r = new StreamReader(rs.GetResponseStream())) return r.ReadToEnd();
        }
        catch (WebException) { return null; }
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
    // Silent: every request is read and never answered, the line being up
    // and the server not, which a look must not wait out.
    public volatile bool Silent;
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
                if (Silent) { Thread.Sleep(5000); return; }
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
