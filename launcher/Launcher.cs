// LavaReborn.exe: the one file a player is handed.
//
// It carries what is not the game -- the Flash projector, our string table
// and the window's photograph -- and it does the two things that are not the
// player's job: it asks for the password itself, and it hands the client a
// session so the client does not ask again. The game stays the player's own
// res/ folder; this reads it and never writes to it.
//
// The path in (see LocalServer for why it has to be HTTP):
//
//   launcher            player types login and password
//   launcher -> server  hello / login / cmdAck, on the game socket itself
//   launcher            starts a web server on 127.0.0.1 over the player's res/
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
    const string REGISTER_URL = "@REGISTER@";
    const string LOST_URL = "@LOST@";
    const string TITLE = "Lava Reborn";

    static string here, res;
    static string player;                 // the unpacked projector
    static readonly ManualResetEvent playerReady = new ManualResetEvent(false);
    static LoginForm form;
    static LocalServer server;
    static string savedLogin, savedHash;

    [STAThread]
    static int Main()
    {
        try { return Run(); }
        catch (Exception e)
        {
            Notice.Show("Не удалось запустить игру", e.Message);
            return 1;
        }
    }

    static int Run()
    {
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        Theme.Init();

        here = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        res = Path.Combine(here, "res");
        if (!File.Exists(Path.Combine(res, "main.swf")))
        {
            Notice.Show("Рядом нет папки res",
                "Положите эту программу туда, где лежит ваша папка res, так " +
                "чтобы получился путь:\n\n" + Path.Combine(res, "main.swf") + "\n\n" +
                "Игра в раздачу не входит — это ваша собственная копия клиента.");
            return 1;
        }

        // An escape hatch for a machine where the web path does not work out:
        // the old behaviour, client off the disk, its own login window.
        // Documented in README.txt so it can be tried without a new build.
        if (Flag("LAVA_LOCAL"))
        {
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
    }

    static void Submit(string login, string password, bool remember)
    {
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
                Say(delegate { form.Error("Не удалось запустить игру: " + e.Message); });
            }
        });
    }

    // The path this launcher exists for. See LocalServer for the why.
    static void LaunchWeb(string hash)
    {
        Log.Start();
        server = new LocalServer(res, Bytes("texts.xml"), HOST, PORT);
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
            gameWnd = GameWindow.Find(game, 20000);
            GameWindow.Park(gameWnd);
            if (revealed) GameWindow.Reveal(gameWnd);   // lost the race; show it now
            GameWindow.Title(gameWnd, TITLE, game);
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

    static bool revealed;
    static IntPtr gameWnd;
    static Process gameProc;

    static void Done()
    {
        if (revealed) return;
        revealed = true;
        Start(delegate
        {
            // The game was started hidden, so showing it is not optional: if
            // the window was never found, look once more rather than leave a
            // running game nobody can see. Revealed first, hidden second --
            // the other order leaves a moment with neither window on screen.
            IntPtr h = gameWnd;
            if (h == IntPtr.Zero && gameProc != null && !gameProc.HasExited)
                h = GameWindow.Find(gameProc, 3000);
            GameWindow.Reveal(h);
            Say(delegate { form.Hide(); });
        });
    }

    // The old way out, kept for a machine where the web path fails: the client
    // runs off the disk in LOCAL mode and asks for the password itself. Then
    // the two files it is missing have to be put in place by hand, and the
    // folder has to be trusted, or Flash will not open a socket at all.
    static void LaunchLocal()
    {
        string texts = Path.Combine(res, "database", "texts.xml");
        if (!File.Exists(texts))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(texts));
            File.WriteAllBytes(texts, Bytes("texts.xml"));
        }
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
