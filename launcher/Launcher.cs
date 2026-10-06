// LavaReborn.exe: the one file a player is handed.
//
// It carries the Flash projector and the window's photograph, and it does
// what is not the player's job: it installs the game into res/ beside itself
// and keeps it the published release (Sync, client/FORMAT.md), it replaces
// itself when a newer launcher is published, it asks for the password, and
// it hands the client a session so the client does not ask again.
//
// The path in (see LocalServer for why it has to be HTTP):
//
//   launcher            res/ checked against the signed release, updated
//   launcher            player types login and password
//   launcher -> server  hello / login / cmdAck, on the game socket itself
//   launcher            starts a web server on 127.0.0.1 over the release
//   launcher -> flash   projector opens http://127.0.0.1:<p>/res/main.swf?logged=1
//   flash    -> launcher  GET /res/xmldocs/csettings_v1.xml   -> PATHTYPE = WEB
//   flash    -> launcher  POST /exe/lavaclient/loaduser/?ajax -> host:port hash
//   flash    -> server  hello / login / cmdAck, and then selPers by itself
//
// The client's own login window is never reached, and with a character on the
// account PersGenerator.selectDefaultPers picks it without being asked, so
// the next thing the player sees is the world.
//
// Built by launcher/build.ps1 with csc.exe out of the Windows .NET Framework,
// so there is nothing to install to produce it.
using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

// What Windows itself says about the file: the name in Explorer's details, in
// Task Manager and on a SmartScreen prompt. Without these it reports the file
// name and nothing else, which for an unsigned exe is exactly the moment a
// player decides whether to trust it.
[assembly: AssemblyTitle("Lava Reborn")]
[assembly: AssemblyProduct("Lava Reborn")]
[assembly: AssemblyDescription("Клиент LAVA Online")]
[assembly: AssemblyVersion("@FILEVERSION@")]
[assembly: AssemblyFileVersion("@FILEVERSION@")]

static class Launcher
{
    // Filled in at build time by build.ps1.
    const string HOST = "@HOST@";
    const int PORT = @PORT@;
    const string VERSION = "@VERSION@";
    // Where the launcher itself and the resource manifest are published.
    // Separate from HOST because they are separate things: build.ps1 takes
    // -ServerHost and -Site apart, and its own documented example gives them
    // different values.
    const string SITE = "@SITE@";
    const string REGISTER_URL = "@REGISTER@";
    const string LOST_URL = "@LOST@";
    const string TITLE = "Lava Reborn";
    // This build's number (launcher/VERSION): a published launcher with a
    // larger one replaces this exe.
    const int BUILD = @BUILD@;
    // The keys a release and a launcher must be signed with (client/keys/).
    static readonly string[] RESOURCE_KEYS = { @RESOURCE_KEYS@ };
    static readonly string[] LAUNCHER_KEYS = { @LAUNCHER_KEYS@ };

    static string here, res, exe;
    static string player;                 // the unpacked projector
    static readonly ManualResetEvent playerReady = new ManualResetEvent(false);
    static LoginForm form;
    static LocalServer server;
    static Sync sync;
    static Mutex single;
    static string savedLogin, savedHash;
    static int restarting;

    [STAThread]
    static int Main(string[] args)
    {
        try { return Run(args); }
        catch (Exception e)
        {
            Notice.Show("Не удалось запустить игру", e.Message);
            return 1;
        }
    }

    static int Run(string[] args)
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Theme.Init();

        exe = Assembly.GetExecutingAssembly().Location;
        here = Path.GetDirectoryName(exe);
        res = Path.Combine(here, "res");
        bool updated = Has(args, "--updated");

        // One launcher per game folder: two would update the same files at
        // once. A launcher that has just replaced itself starts the new one
        // and exits, so the new one waits for the folder rather than give up.
        bool mine;
        single = new Mutex(true, @"Local\LavaReborn-" + Hashes.Sha256Hex(
            Encoding.UTF8.GetBytes(here.ToLowerInvariant())).Substring(0, 16), out mine);
        if (!mine)
        {
            try { mine = single.WaitOne(updated ? 15000 : 0); }
            catch (AbandonedMutexException) { mine = true; }
            if (!mine)
            {
                Notice.Show("Лаунчер уже запущен", "Для этой папки игры уже открыт лаунчер.");
                return 1;
            }
        }
        Start(delegate { Sync.CleanOld(exe); });

        sync = new Sync(here, SITE + "/download/client/", new KeySet(RESOURCE_KEYS),
                        new KeySet(LAUNCHER_KEYS), BUILD, exe);
        sync.FullVerify = Has(args, "--verify");
        sync.ManualUrl = SITE + "/download/LavaReborn.exe";

        // An escape hatch for a machine where the web path does not work out:
        // the old behaviour, client off the disk, its own login window. It
        // plays the release as installed, so the launcher has to have run
        // the normal way once. Documented in README.txt.
        if (Flag("LAVA_LOCAL"))
        {
            if (!File.Exists(Path.Combine(res, "main.swf")) ||
                !File.Exists(Path.Combine(res, "database", "texts.xml")))
            {
                Notice.Show("Игра ещё не установлена",
                    "Запустите лаунчер один раз обычным образом: он скачает игру в папку\n\n" + res);
                return 1;
            }
            LaunchLocal();
            return 0;
        }

        form = new LoginForm(LoadHero(), VERSION);
        savedLogin = Creds.Load(out savedHash);
        if (savedLogin != null) form.Fill(savedLogin, true);

        form.Submit += Submit;
        form.Register += delegate { Browse(REGISTER_URL); };
        form.LostPassword += delegate
        {
            Browse(LOST_URL);
            form.Note("Пароль хранится только как хеш и восстановлению не подлежит — " +
                      "новый выдаёт администратор.");
        };
        form.Shown += delegate { Background(); };

        Application.Run(form);
        return 0;
    }

    // Unpacking 16 MB and asking the server whether it is up both happen while
    // the player is still reading the window.
    static void Background()
    {
        Start(delegate
        {
            try { player = Unpack(); }
            catch (Exception e) { Say(delegate { form.Error("Не удалось распаковать проигрыватель: " + e.Message); }); }
            playerReady.Set();
        });

        Start(delegate
        {
            bool up = GameProbe.Ping(HOST, PORT);
            Say(delegate
            {
                form.Status(up, up ? "Сервер доступен" : "Сервер недоступен");
            });
        });

        // The release check runs beside those two, and unlike them it owns the
        // way in: until every file of the game is the published one, the
        // button is not "Войти". Sync.Start returns at once and works on its
        // own thread, so this costs the window nothing.
        sync.Changed = delegate { Say(ShowUpdate); };
        sync.Start();
        ShowUpdate();
    }

    // The one place that turns an update state into something on screen.
    static void ShowUpdate()
    {
        if (form == null || form.GameStarted) return;
        long done, total;
        int files, fileTotal;
        sync.Progress(out done, out total, out files, out fileTotal);
        switch (sync.State)
        {
            case SyncState.Checking:
                form.Gate(sync.Note, "Проверяем обновления", null, false);
                break;
            case SyncState.Scanning:
                form.Gate(sync.Note + ": " + Percent(done, total), "Проверяем файлы", null, false);
                break;
            case SyncState.Downloading:
                form.Gate(sync.Note + ": " + Mb(done) + " из " + Mb(total) + " МБ" +
                          (fileTotal > 0 ? ", файлов " + files + " из " + fileTotal : ""),
                          "Загрузка", null, false);
                break;
            case SyncState.Restarting:
                form.Gate(sync.Note, "Перезапуск", null, true);
                Restart();
                break;
            case SyncState.MustUpdate:
                form.Gate(sync.Note, "Скачать новую версию",
                          delegate { Browse(sync.ManualUrl); }, true);
                break;
            case SyncState.Failed:
                form.Gate(sync.Note, "Повторить", delegate { sync.Start(); }, false);
                break;
            default:
                // Ready, or the server could not be asked and the folder is
                // still the release last accepted. Either way the way in is
                // open -- refusing to start because a web server is down
                // would lock every player out of a game that is running.
                form.Ungate();
                // Not over an error. The unpacking thread can fail while this
                // one is still on the network, and its message is the only
                // account of why the game will not start -- an update line
                // written over it leaves the player with nothing to read.
                if (!form.ErrorShown) form.Note(sync.Note);
                break;
        }
    }

    static string Mb(long bytes)
    {
        return (bytes / 1048576.0).ToString("0.0", System.Globalization.CultureInfo.GetCultureInfo("ru-RU"));
    }

    static string Percent(long done, long total)
    {
        return total <= 0 ? "0%" : ((int)(100.0 * done / total)).ToString() + "%";
    }

    // The new exe is already in place under this one's name; start it and go.
    // The mutex is let go first so the new one does not wait it out.
    static void Restart()
    {
        if (Interlocked.Exchange(ref restarting, 1) != 0) return;
        try
        {
            Process.Start(new ProcessStartInfo(exe, "--updated") { UseShellExecute = false, WorkingDirectory = here });
        }
        catch (Exception e)
        {
            Notice.Show("Лаунчер обновлён", "Запустите его ещё раз: " + e.Message);
        }
        try { single.ReleaseMutex(); } catch { }
        Environment.Exit(0);
    }

    static void Submit(string login, string password, bool remember)
    {
        // The form will not call this while it is gated; this is the second
        // lock on the same door, for the day somebody wires up another way in.
        if (!sync.Playable)
        {
            ShowUpdate();
            return;
        }
        form.Busy(true, "Входим");
        form.Note("Проверяем учётные данные");

        Start(delegate
        {
            // A remembered account is remembered by its digest -- that is the
            // whole credential, and the password it came from is not kept
            // anywhere. So an untouched password box on the remembered login
            // means: use what we have.
            string hash;
            if (form.PasswordRemembered && savedHash != null &&
                string.Equals(login, savedLogin, StringComparison.OrdinalIgnoreCase))
                hash = savedHash;
            else
                hash = Creds.Hash(password, login);

            Verdict v = GameProbe.Check(HOST, PORT, hash);
            if (v != Verdict.Ok)
            {
                Say(delegate
                {
                    switch (v)
                    {
                        case Verdict.BadCredentials:
                            form.Error("Неверный логин или пароль");
                            break;
                        case Verdict.Banned:
                            form.Error("Учётная запись заблокирована");
                            break;
                        case Verdict.Unreachable:
                            form.Error("Сервер не отвечает — попробуйте позже");
                            form.Status(false, "Сервер недоступен");
                            break;
                        default:
                            form.Error("Сервер ответил неожиданно");
                            break;
                    }
                });
                return;
            }

            if (remember) Creds.Save(login, hash);
            else Creds.Forget();
            savedLogin = login;
            savedHash = hash;

            Say(delegate { form.Note("Запускаем игру"); });
            playerReady.WaitOne();
            if (player == null) return;

            try { LaunchWeb(hash); }
            catch (Exception e)
            {
                // Let the door shut again. launched is a guard against two
                // clicks landing together, not a one-shot fuse: if the
                // projector could not be started -- an antivirus took the
                // unpacked player, the disk filled -- the player has to be
                // able to try again without closing the launcher.
                Interlocked.Exchange(ref launched, 0);
                Say(delegate { form.Error("Не удалось запустить игру: " + e.Message); });
            }
        });
    }

    // The path this launcher exists for. See LocalServer for the why.
    static void LaunchWeb(string hash)
    {
        // One click, one game. The button is disabled while the login is in
        // flight, but the check runs on a worker thread and a second click
        // landing before it returns gets here too -- and two projectors is
        // two windows, one of them the empty one that was reported. Exchange
        // rather than a bool, because the two clicks are on two threads.
        if (Interlocked.Exchange(ref launched, 1) != 0) return;
        Log.Start();
        // The 16:9 wrapper is opt-in, and it is opt-in for a reason that was
        // seen rather than feared. Inside it the world is drawn correctly --
        // right size, nothing cut off -- and then the client stops taking
        // mouse clicks, which in this game means the character cannot walk,
        // because walking is a click on the ground.
        //
        // The cause is not settled, and one suspicion is now ruled out. It
        // used to be the keeper: it re-asserts Stage.scaleMode 25 times a
        // second, every such assignment fires onResize at every Stage
        // listener, and SceneShifter's onResize (SceneShifter.as:56-58) is
        // setMCSize, which rebuilds the layout. But wrapper_plain.swf -- the
        // same film with no scaling at all, main.swf's own 950x650 stage, the
        // game at the origin, not one word said to Stage -- loses the clicks
        // just the same: on 2026-09-29 six left clicks posted to the
        // projector's window walked the character four times on main.swf
        // and not once in either film. So it is something about the game
        // being loaded into a clip, not about the stage.
        //
        // Until that is found and cured, the default is the client as it
        // was drawn: main.swf on level 0, 950x650, nothing in the way.
        // LAVA_SCALE=1 brings the 16:9 wrapper back for whoever is working on
        // it, LAVA_PLAIN=1 the unscaled one.
        //
        // Both films carry the ClanInspector mend (tools/make_wrapper.py,
        // CLAN INSPECTOR) -- the clan window no longer goes deaf after a
        // reconnect, and the founding page shows its price -- and only the
        // films can carry it, because it has to run inside the client. So
        // that mend reaches players the day the clicks are cured and a film
        // becomes the default, and not before.
        byte[] wrapper = null;
        if (Flag("LAVA_SCALE"))
        {
            // A film that cannot be read is a smaller game, not a dead
            // launcher: fall back rather than refuse to start.
            try { wrapper = Bytes("wrapper.swf"); }
            catch { wrapper = null; }
        }
        // What the projector is pointed at. The plain film has main.swf's own
        // stage, so nothing about the window changes for it: no Stage() and
        // no Zoom, the built-in 950x650 stands. Unreadable -> the bare game,
        // for the same reason as above.
        byte[] film = wrapper;
        if (film == null && Flag("LAVA_PLAIN"))
        {
            try { film = Bytes("wrapper_plain.swf"); }
            catch { film = null; }
        }
        if (wrapper != null)
        {
            // The window is cut to the wrapper's stage, and by default to
            // exactly that size: one pixel for one pixel, nothing stretched.
            // What makes the picture bigger is the wider stage itself --
            // the game lays out into it -- not magnification.
            //
            // LAVA_SCALE therefore changes the window and never the field.
            // Every value but the default is enlargement, and enlargement is
            // the softness that was complained about: there are 1280x720 real
            // pixels and no more. fit fills the desktop, 1.5 asks for one and
            // a half times the stage's own size, and so on.
            Stage(wrapper);
            GameWindow.Zoom = 1;
            string want = (Environment.GetEnvironmentVariable("LAVA_SCALE") ?? "").Trim();
            double zoom;
            if (want.Equals("fit", StringComparison.OrdinalIgnoreCase) ||
                want.Equals("max", StringComparison.OrdinalIgnoreCase))
                GameWindow.Zoom = 0;                       // as large as the desktop allows
            else if (double.TryParse(want, System.Globalization.NumberStyles.Float,
                                     System.Globalization.CultureInfo.InvariantCulture,
                                     out zoom) && zoom > 0.1)
                GameWindow.Zoom = zoom;
        }
        // The release the files were checked against. Submit only gets here
        // when Sync says the folder is playable, so it is there.
        server = new LocalServer(sync, film, HOST, PORT);
        server.Hash = hash;
        server.WorldLoading += delegate { Start(Settle); };
        server.Start();

        // Hidden, and kept off screen by GameWindow until there is a world in
        // it: the client draws its own login frame on the way in whatever we
        // do, and this is what keeps the player from seeing it.
        Process game = Process.Start(new ProcessStartInfo(player, "\"" + server.MovieUrl() + "\"")
        {
            UseShellExecute = false,
            WindowStyle = ProcessWindowStyle.Hidden,
            WorkingDirectory = here,
        });
        gameProc = game;

        Start(delegate
        {
            // Find takes as long as the projector takes to open its window,
            // so it is deliberately outside the lock; only the decision that
            // follows it is not.
            IntPtr h = GameWindow.Find(game, 20000);
            lock (windowLock)
            {
                gameWnd = h;
                // Parking a window the world is already showing in is how the
                // game ends up back at -32000 after it was revealed. Whoever
                // gets here second does what the first one decided.
                if (revealed) GameWindow.Reveal(h);
                else GameWindow.Park(h);
            }
            GameWindow.Title(h, TITLE, game);
        });
        Start(delegate
        {
            // Whichever comes first: the world, or long enough that something
            // has clearly gone wrong -- and then the game is shown anyway,
            // because its own error message is the one that says what
            // happened, and an invisible game says nothing at all.
            if (!game.WaitForExit(25000)) Say(Done);
        });
        Start(delegate
        {
            game.WaitForExit();
            // The web server is the game's res/ folder; it lives exactly as
            // long as the game does.
            if (server != null) server.Stop();
            Environment.Exit(0);
        });

        Say(delegate
        {
            form.Note("Загрузка мира");
            // Belt and braces: if parking the game's window ever fails, this
            // window is still the one in front of it.
            form.Front();
        });
    }

    // The first location request means the world is being built, not that it
    // is on screen: the library, the sprites and the player's own figure are
    // still coming. Rather than guess at how long that takes on someone
    // else's disk, wait for the client to stop asking for anything.
    static void Settle()
    {
        int cap = Environment.TickCount + 10000;
        while (Environment.TickCount < cap)
        {
            if (Environment.TickCount - server.LastRequest > 600) break;
            Thread.Sleep(80);
        }
        Say(Done);
    }

    // revealed and gameWnd are written by the thread that finds the window and
    // read by the thread that shows it, and either can be first: the world can
    // settle before the projector has drawn a window, and a slow disk can put
    // the window first. windowLock is what makes the pair of them one decision.
    static readonly object windowLock = new object();
    static bool revealed;
    static IntPtr gameWnd;
    static Process gameProc;
    static int launched;

    static void Done()
    {
        lock (windowLock)
        {
            if (revealed) return;       // Settle and the timeout both call this
            revealed = true;
        }
        Start(delegate
        {
            // The game was started hidden, so showing it is not optional: if
            // the window was never found, look once more rather than leave a
            // running game nobody can see. Revealed first, hidden second --
            // the other order leaves a moment with neither window on screen.
            IntPtr h;
            lock (windowLock) h = gameWnd;
            if (h == IntPtr.Zero && gameProc != null && !gameProc.HasExited)
                h = GameWindow.Find(gameProc, 3000);
            lock (windowLock)
            {
                if (gameWnd == IntPtr.Zero) gameWnd = h;
                GameWindow.Reveal(gameWnd);
            }
            Say(delegate { form.Hide(); });
        });
    }

    // The old way out, kept for a machine where the web path fails: the client
    // runs off the disk in LOCAL mode and asks for the password itself. The
    // files it needs are the release's, already in res/; the folder has to be
    // trusted, or Flash will not open a socket at all.
    static void LaunchLocal()
    {
        Trust();

        string exe = Unpack();
        string url = Path.Combine(res, "main.swf") +
                     "?vversion=1&var_host=" + HOST + "&var_port=" + PORT;
        Process game = Process.Start(new ProcessStartInfo(exe, "\"" + url + "\"")
        {
            UseShellExecute = false,
            WorkingDirectory = here,
        });
        // Nothing to hide here: this path goes to the client's own login
        // window on purpose, so the window only gets its name.
        GameWindow.Title(GameWindow.Find(game, 20000), TITLE, game);
    }

    // --- plumbing ---------------------------------------------------------

    static void Start(ThreadStart work)
    {
        Thread t = new Thread(work);
        t.IsBackground = true;
        t.Start();
    }

    // Anything a worker wants to say to the window has to be said on the
    // window's own thread.
    static void Say(MethodInvoker what)
    {
        try
        {
            if (form != null && form.IsHandleCreated) form.BeginInvoke(what);
        }
        catch { }
    }

    // The wrapper's stage, read out of its own header so the size lives in
    // one place. Our wrapper is written uncompressed (FWS), so the header is
    // right there: a RECT of four signed fields, each as many bits wide as
    // the five bits in front of them say, in twips.
    static void Stage(byte[] swf)
    {
        try
        {
            int nbits = swf[8] >> 3, at = 5;
            int[] v = new int[4];
            for (int i = 0; i < 4; i++)
            {
                int n = 0;
                for (int b = 0; b < nbits; b++, at++)
                    n = (n << 1) | ((swf[8 + (at >> 3)] >> (7 - (at & 7))) & 1);
                v[i] = n;
            }
            GameWindow.SetArt((v[1] - v[0]) / 20, (v[3] - v[2]) / 20);
        }
        catch { /* the built-in 950x650 stands */ }
    }

    static bool Has(string[] args, string flag)
    {
        foreach (string a in args)
            if (string.Equals(a, flag, StringComparison.OrdinalIgnoreCase)) return true;
        return false;
    }

    static bool Flag(string name)
    {
        string v = Environment.GetEnvironmentVariable(name);
        if (v == null) return false;
        v = v.Trim().ToLowerInvariant();
        return v != "" && v != "0" && v != "no" && v != "off" && v != "false";
    }

    static void Browse(string url)
    {
        try { Process.Start(url); }
        catch { }
    }

    // The projector is unpacked once and kept: it is 16 MB, and writing it out
    // on every start would be both slow and pointless. A size mismatch means a
    // half-written or older copy, so it is redone.
    static string Unpack()
    {
        string dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "LavaOnline");
        Directory.CreateDirectory(dir);
        string path = Path.Combine(dir, "flashplayer.exe");
        using (Stream src = Open("fp32_sa.exe"))
        {
            if (!File.Exists(path) || new FileInfo(path).Length != src.Length)
                using (FileStream dst = File.Create(path))
                    src.CopyTo(dst);
        }
        return path;
    }

    static Image LoadHero()
    {
        try
        {
            using (Stream s = Open("hero.jpg"))
                return Image.FromStream(s);
        }
        catch { return null; }
    }

    static byte[] Bytes(string name)
    {
        using (Stream s = Open(name))
        using (MemoryStream m = new MemoryStream())
        {
            s.CopyTo(m);
            return m.ToArray();
        }
    }

    static Stream Open(string name)
    {
        Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(name);
        if (s == null)
            throw new InvalidOperationException("В этой сборке нет вложенного файла " + name + ".");
        return s;
    }

    // Only the local fallback needs this: a movie loaded over HTTP is in the
    // remote sandbox, where the trust list does not apply and the socket is
    // allowed by the server's own policy instead. Off the disk, without this
    // line, the login window appears and the play button answers that the
    // connection was not established, while the server never sees a byte.
    static void Trust()
    {
        try
        {
            string dir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData),
                @"Macromedia\Flash Player\#Security\FlashPlayerTrust");
            Directory.CreateDirectory(dir);
            string cfg = Path.Combine(dir, "lava.cfg");
            string line = here.TrimEnd('\\');
            if (File.Exists(cfg))
            {
                foreach (string s in File.ReadAllLines(cfg))
                    if (s.Trim().Equals(line, StringComparison.OrdinalIgnoreCase))
                        return;
                File.AppendAllText(cfg, line + "\r\n", Encoding.Default);
            }
            else File.WriteAllText(cfg, line + "\r\n", Encoding.Default);
        }
        catch (Exception e)
        {
            Notice.Show("Не удалось разрешить игре выход в сеть",
                e.Message + "\n\nСоздайте вручную файл\n\n" +
                @"%APPDATA%\Macromedia\Flash Player\#Security\FlashPlayerTrust\lava.cfg" +
                "\n\nи впишите в него одну строку — путь к этой папке:\n\n" + here);
        }
    }
}
