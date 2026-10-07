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
using System.Collections.Generic;
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
    const string FORUM_URL = "@FORUM@";
    const string NEWS_URL = "@NEWS@";
    const string WIKI_URL = "@WIKI@";
    const string CABINET_URL = "@CABINET@";
    const string TITLE = "Lava Reborn";
    // This build's number (the gate counts them, launcher/build.sh): a
    // published launcher with a larger one replaces this exe.
    const int BUILD = @BUILD@;
    // The keys a release and a launcher must be signed with (client/keys/).
    static readonly string[] RESOURCE_KEYS = { @RESOURCE_KEYS@ };
    static readonly string[] LAUNCHER_KEYS = { @LAUNCHER_KEYS@ };

    static string here, exe;              // the exe and its folder
    static string gameDir, res;           // the game folder and its res\
    static string player;                 // the unpacked projector
    static readonly ManualResetEvent playerReady = new ManualResetEvent(false);
    static MainForm form;
    static LocalServer server;
    static Sync sync;
    static Mutex single;
    static string savedLogin, savedHash, savedName;
    static int restarting;

    // What the window is built from, all on the UI thread.
    static bool? serverUp;                // null: not answered yet
    static bool signedIn;
    static string hash;                   // the credential of the account shown
    static string who = "";               // its character's name
    static bool busy;                     // the password is being checked
    static bool launching;                // the game is being started
    static string launchError;            // why the game did not start, if it did not
    static bool newsPending;              // show "Что нового" until it is opened

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
        // The game folder: the one the player chose in the window, else the
        // one beside the exe, as before.
        gameDir = Prefs.Get(Prefs.GameDir);
        if (string.IsNullOrEmpty(gameDir) || !Directory.Exists(gameDir)) gameDir = here;
        res = Path.Combine(gameDir, "res");
        bool updated = Has(args, "--updated");

        // One launcher per game folder: two would update the same files at
        // once. A launcher that has just replaced itself starts the new one
        // and exits, so the new one waits for the folder rather than give up.
        bool mine;
        single = new Mutex(true, LockName(gameDir), out mine);
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

        sync = NewSync(gameDir);
        sync.FullVerify = Has(args, "--verify");

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

        form = new MainForm(LoadImage("hero.jpg"), LoadImage("logo.png"));
        // The whole build under the panel: number, date and commit.
        form.Panel.VersionLabel = VERSION.StartsWith("v") ? VERSION : "v" + VERSION;
        form.Panel.VersionTip = "Сборка " + VERSION;

        // "Что нового" appears once after the launcher has changed under the
        // player, and stays until the news is opened. A first start has no
        // "before" to compare with, so it just records this build.
        string seen = Prefs.Get(Prefs.SeenVersion);
        if (seen == null) Prefs.Set(Prefs.SeenVersion, BUILD.ToString());
        else newsPending = seen != BUILD.ToString();

        savedLogin = Creds.Load(out savedHash, out savedName);
        if (savedLogin != null && Prefs.Get(Prefs.SignedOut) == null)
        {
            // The remembered digest is the whole credential, so the account
            // is shown at once; the server is asked again in the background,
            // and a refusal sends the form back to the login.
            signedIn = true;
            hash = savedHash;
            who = string.IsNullOrEmpty(savedName) ? savedLogin : savedName;
            form.Auth.ShowAccount(who, "", "");
        }
        else
        {
            // Signed out of a remembered account: the login, with the name
            // and the remembered password, one press from the card again.
            form.Auth.ShowLogin();
            if (savedLogin != null) form.Auth.Fill(savedLogin, true);
        }

        form.Auth.Submit += Submit;
        form.Auth.Register += delegate { Browse(REGISTER_URL); };
        form.Auth.LostPassword += delegate
        {
            new TextDialog("Забыли пароль?", new[] {
                "Если ты не помнишь пароль, обратись к администратору. Старый пароль " +
                "восстановить нельзя, администратор выдаст новый." }, null, null).Open(form);
        };
        form.Auth.Logout += Logout;
        form.Auth.About += delegate { Browse(SITE); };
        form.Auth.Wiki += delegate { Browse(WIKI_URL); };
        form.Auth.Cabinet += delegate { Browse(CABINET_URL); };
        form.Settings += OpenSettings;
        form.Forum += delegate { Browse(FORUM_URL); };
        form.Panel.Play += Play;
        form.Panel.Action += PanelAction;
        form.Panel.VersionClick += OpenNews;
        form.Panel.NewsClick += OpenNews;
        form.Panel.FolderClick += delegate { PickFolder(); };
        form.Shown += delegate { Background(); };

        Render();
        TrayOn();
        Application.Run(form);
        return 0;
    }

    // --- the game folder --------------------------------------------------

    static Sync NewSync(string dir)
    {
        Sync s = new Sync(dir, SITE + "/download/client/", new KeySet(RESOURCE_KEYS),
                          new KeySet(LAUNCHER_KEYS), BUILD, exe);
        s.ManualUrl = SITE + "/download/LavaReborn.exe";
        // A first install asks first, the way the concept shows it: folder,
        // size, free space, "Начать загрузку".
        s.AskFirst = true;
        return s;
    }

    // One launcher per game folder, by this name.
    static string LockName(string dir)
    {
        return @"Local\LavaReborn-" + Hashes.Sha256Hex(
            Encoding.UTF8.GetBytes(Path.GetFullPath(dir).TrimEnd('\\').ToLowerInvariant())).Substring(0, 16);
    }

    static bool HasGame(string dir)
    {
        try { return File.Exists(Path.Combine(dir, "res", "main.swf")); }
        catch { return false; }
    }

    // A new folder is a new Sync, a new lock and a new memory (.lava/ lives
    // in the game folder). All three are swapped in this window, with no
    // restart: the old run is held and waited out, the game carried over if
    // it has to be, and the new folder checked as on a start.
    static void PickFolder()
    {
        if (switching || launching) return;
        string from = gameDir;
        bool installed = HasGame(from) || Downloaded(from);
        string p;
        using (FolderBrowserDialog d = new FolderBrowserDialog())
        {
            d.Description = installed ? "Выбери пустую папку для переноса или папку с игрой."
                                      : "Выбери папку со своей копией игры.";
            d.ShowNewFolderButton = true;
            try { d.SelectedPath = gameDir; } catch { }
            if (d.ShowDialog(form) != DialogResult.OK) return;
            p = d.SelectedPath;
        }
        // res\ itself was picked: its parent is the game folder.
        if (!HasGame(p) && File.Exists(Path.Combine(p, "main.swf"))) p = Path.GetDirectoryName(p);
        p = Path.GetFullPath(p).TrimEnd('\\');
        if (string.Equals(p, from.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase)) return;
        // A folder inside what would be moved cannot take it.
        foreach (string name in CARRIED)
            if ((p + "\\").StartsWith(Path.Combine(from, name) + "\\", StringComparison.OrdinalIgnoreCase)) return;

        // The new folder's lock before anything is touched: another launcher
        // may already be keeping it. Taken here, on the window's thread, and
        // let go on it too, as a mutex insists.
        bool mine;
        Mutex next = new Mutex(true, LockName(p), out mine);
        if (!mine)
        {
            next.Close();
            new TextDialog("Лаунчер уже запущен", new[] { "Для этой папки игры уже открыт лаунчер." }, null, null).Open(form);
            return;
        }

        // A folder that already holds a game is switched to as it is; an
        // installed game, or a download under way, goes along to any other.
        bool carry = installed && !HasGame(p);
        switching = true;
        moving = carry;
        moveDone = moveTotal = 0;
        Sync old = sync;
        old.Hold();
        Render();
        Start(delegate
        {
            string[] error = null;
            try
            {
                // The files are Sync's until its run is over: a download ends
                // between blocks, a check before anything is fetched.
                old.Wait(Timeout.Infinite);
                if (carry) Carry(from, p);
            }
            catch (NoRoomException e)
            {
                error = new[] { "Недостаточно места",
                    "Для переноса нужно " + Theme.Size(e.Need) + ", свободно " + Theme.Size(e.Free) +
                    ". Игра осталась в прежней папке." };
            }
            catch (Exception e)
            {
                error = new[] { "Не удалось перенести игру",
                    "Игра осталась в прежней папке. Все файлы сохранены.", e.Message };
            }
            Say(delegate
            {
                switching = moving = false;
                if (error != null)
                {
                    try { next.ReleaseMutex(); } catch { }
                    next.Close();
                    Render();
                    string[] body = new string[error.Length - 1];
                    Array.Copy(error, 1, body, 0, body.Length);
                    new TextDialog(error[0], body, null, null).Open(form);
                    // The run that was held for the move goes on where it was.
                    if (sync.State == SyncState.Paused) sync.Start();
                    return;
                }
                Prefs.Set(Prefs.GameDir, p);
                old.Changed = null;
                try { single.ReleaseMutex(); } catch { }
                single.Close();
                single = next;
                gameDir = p;
                res = Path.Combine(p, "res");
                samples.Clear();
                sync = NewSync(p);
                sync.Changed = delegate { Say(Render); };
                sync.Start();
                if (settings != null) settings.SetFolder(gameDir);
                Render();
            });
        });
    }
    // --- moving the game along with the folder ---------------------------------

    // What of the game folder is the game: the files and the launcher's
    // memory of them. The exe and anything else beside them stay.
    static readonly string[] CARRIED = { "res", ".lava" };
    static volatile bool moving;
    static volatile bool switching;      // the folder is being changed; moving: and the game carried
    static long moveDone, moveTotal;
    static int moveTick;

    // A download begun and not finished is worth carrying too.
    static bool Downloaded(string dir)
    {
        try
        {
            string staging = Path.Combine(Path.Combine(dir, ".lava"), "staging");
            return Directory.Exists(staging) && Directory.GetFiles(staging).Length > 0;
        }
        catch { return false; }
    }

    class NoRoomException : Exception
    {
        public readonly long Need, Free;
        public NoRoomException(long need, long free) { Need = need; Free = free; }
    }

    // On the same drive a rename, at once. Across drives a copy, every byte
    // over before the old copy is let go, and a failed copy takes back what
    // it wrote. File.Copy keeps the modification time, so .lava\index.tsv
    // still vouches for every file and the new folder is not hashed again.
    static void Carry(string from, string to)
    {
        Directory.CreateDirectory(to);
        bool sameDrive = string.Equals(Path.GetPathRoot(Path.GetFullPath(from)),
                                       Path.GetPathRoot(Path.GetFullPath(to)), StringComparison.OrdinalIgnoreCase);
        List<string> renamed = new List<string>();
        List<string[]> copies = new List<string[]>();
        long total = 0;
        try
        {
            foreach (string name in CARRIED)
            {
                string src = Path.Combine(from, name), dst = Path.Combine(to, name);
                if (!Directory.Exists(src)) continue;
                if (sameDrive && !Directory.Exists(dst))
                {
                    Directory.Move(src, dst);
                    renamed.Add(name);
                    continue;
                }
                foreach (string f in Directory.GetFiles(src, "*", SearchOption.AllDirectories))
                {
                    copies.Add(new[] { f, dst + f.Substring(src.Length) });
                    total += new FileInfo(f).Length;
                }
            }
            if (copies.Count > 0)
            {
                long free = long.MaxValue;
                try { free = new DriveInfo(Path.GetPathRoot(Path.GetFullPath(to))).AvailableFreeSpace; }
                catch { }
                if (free < total + 64L * 1024 * 1024) throw new NoRoomException(total, free);
                Interlocked.Exchange(ref moveTotal, total);
                List<string> made = new List<string>();
                try
                {
                    foreach (string[] c in copies)
                    {
                        Directory.CreateDirectory(Path.GetDirectoryName(c[1]));
                        if (!File.Exists(c[1])) made.Add(c[1]);
                        File.Copy(c[0], c[1], true);
                        Interlocked.Add(ref moveDone, new FileInfo(c[1]).Length);
                        int now = Environment.TickCount;
                        if (now - moveTick > 200) { moveTick = now; Say(Render); }
                    }
                }
                catch
                {
                    foreach (string m in made) try { File.Delete(m); } catch { }
                    throw;
                }
            }
        }
        catch
        {
            foreach (string name in renamed)
                try { Directory.Move(Path.Combine(to, name), Path.Combine(from, name)); } catch { }
            throw;
        }
        // Everything is over; the old copy goes. What will not go (a file
        // held open by something else) is left, the new folder is whole.
        foreach (string name in CARRIED)
        {
            if (renamed.Contains(name)) continue;
            string src = Path.Combine(from, name);
            if (Directory.Exists(src)) try { Directory.Delete(src, true); } catch { }
        }
    }

    static PanelState Moving()
    {
        long done = Interlocked.Read(ref moveDone), total = Interlocked.Read(ref moveTotal);
        PanelState s = new PanelState();
        s.Title = "Перенос игры";
        s.Icon = "arrow";
        if (total > 0)
        {
            s.Track = true;
            s.Progress = (double)done / total;
            s.Line = "Перенесено: " + OfTotal(done, total);
            s.Right = Percent(done, total);
        }
        return s;
    }

    static SettingsDialog settings;       // open, or null

    static void OpenSettings()
    {
        if (switching) return;
        SyncState st = sync.State;
        bool canVerify = !launching && (st == SyncState.Ready || st == SyncState.Offline ||
                                        st == SyncState.Failed || st == SyncState.Paused);
        SettingsDialog d = new SettingsDialog(gameDir, form.Panel.VersionLabel, canVerify);
        d.ChangeFolder += delegate { PickFolder(); };
        // The folder can change while this is open (it is where the change
        // starts from), and the box has to follow it.
        settings = d;
        d.FormClosed += delegate { settings = null; };
        d.NewsPending = newsPending;
        d.Verify += Verify;
        d.CheckUpdates += CheckNow;
        d.News += OpenNews;
        d.Open(form);
    }

    // "Проверить файлы": every file hashed again, nothing taken from the index.
    static void Verify()
    {
        sync.FullVerify = true;
        sync.Start();
    }

    // "Проверить обновления", in the settings and the tray: a run now, as on a
    // start; a newer launcher replaces this one and restarts, as ever.
    static void CheckNow()
    {
        if (launching || switching) return;
        sync.Start();
        Render();
    }

    static void OpenNews()
    {
        Browse(NEWS_URL);
        if (newsPending)
        {
            newsPending = false;
            Prefs.Set(Prefs.SeenVersion, BUILD.ToString());
            Render();
        }
    }

    // --- what is on screen --------------------------------------------------

    // The one place that turns the facts -- the release check, the server,
    // the account, what is in flight -- into the window. Called on the UI
    // thread whenever any of them moves, and cheap enough for every move.
    static void Render()
    {
        if (form == null) return;
        SyncState st = sync.State;
        if (st == SyncState.Restarting) Restart("--updated");

        // The check after a game: the release was whole a moment ago, so
        // while it only asks, the panel says it is checking and "ИГРАТЬ" stays
        // open (pressed, the game starts when the check is over). It ends
        // when the run has settled, not at the first Ready seen: Sync.Start
        // returns before the run has left the Ready it started from.
        if (quiet)
        {
            bool settled = sync.Wait(0);
            if (!settled && (st == SyncState.Ready || st == SyncState.Checking || st == SyncState.Scanning))
                st = SyncState.Checking;
            else quiet = false;
        }
        PanelState s = Preview() ?? (moving ? Moving() : Panel(switching ? SyncState.Checking : st));
        if (launchError != null && s.Action == null)
        {
            s.Line = launchError;
            s.Right = "";
            s.Tone = Tone.Bad;
        }
        form.Panel.Show(s);
        form.Panel.News = newsPending;
        form.Panel.CanPlay = (sync.Playable || quiet) && signedIn && serverUp != false && !launching && !switching;
        form.Panel.Starting = launching && !inGame && launchError == null;
        form.Panel.InGame = inGame;

        // The login: barred by a launcher that must be replaced or a silent
        // server, which the line under the button explains; otherwise open,
        // with a remark when there is something to remark on.
        bool open = st != SyncState.MustUpdate && serverUp != false;
        form.Auth.Gate(open, busy);
        if (!signedIn && !form.Auth.HintIsBad)
        {
            string hint = "";
            if (busy) hint = "Проверяем учётные данные";
            else if (st == SyncState.MustUpdate) hint = "Вход доступен после обновления лаунчера";
            else if (serverUp == false) hint = "Сервер не отвечает. Попробуй позже.";
            else if (st == SyncState.Scanning) hint = "Проверяем файлы игры";
            else if (st == SyncState.Setup || st == SyncState.Paused ||
                     (st == SyncState.Downloading && sync.Fresh))
                hint = "Можно войти, пока готовятся ресурсы";
            form.Auth.Hint(hint, false);
        }

        form.Auth.Server(serverUp, serverUp == null ? "Проверяем сервер"
                                   : (serverUp.Value ? "Сервер доступен" : "Сервер недоступен"));
    }

    // Numbers the way the concept writes them: thousands apart by a space.
    static string Count(long n)
    {
        System.Globalization.NumberFormatInfo f =
            (System.Globalization.NumberFormatInfo)System.Globalization.NumberFormatInfo.InvariantInfo.Clone();
        f.NumberGroupSeparator = " ";
        return n.ToString("#,0", f);
    }

    // "1,1 из 2,3 МБ": the unit once when it is the same unit.
    static string OfTotal(long a, long b)
    {
        string sa = Theme.Size(a), sb = Theme.Size(b);
        string ua = sa.Substring(sa.LastIndexOf(' ')), ub = sb.Substring(sb.LastIndexOf(' '));
        return (ua == ub ? sa.Substring(0, sa.Length - ua.Length) : sa) + " из " + sb;
    }

    static string Percent(long done, long total)
    {
        return (total > 0 ? (int)Math.Floor(done * 100.0 / total) : 0) + " %";
    }

    static string Needs(long need, long free)
    {
        return "Нужно " + Theme.Size(need) +
               (free == long.MaxValue ? "" : " · Свободно " + Theme.Size(free));
    }

    // An update this large is shown the way an install is.
    const long BIG_UPDATE = 64L * 1024 * 1024;

    static PanelState Panel(SyncState st)
    {
        PanelState s = new PanelState();
        long done, total;
        int files, fileTotal;
        sync.Progress(out done, out total, out files, out fileTotal);
        double part = total > 0 ? (double)done / total : 0;

        switch (st)
        {
            case SyncState.Checking:
                s.Title = "Проверяем обновления";
                s.Icon = "retry";
                s.Track = true;
                s.Busy = true;
                // The line under the track, as the other states with a
                // track have one: the build, and "Что нового" if pending.
                s.Version = true;
                break;
            case SyncState.Restarting:
                s.Title = "Перезапуск лаунчера";
                s.Line = "Подожди, запускаем новую версию";
                s.Icon = "retry";
                break;
            case SyncState.MustUpdate:
                s.Title = "Лаунчер устарел";
                s.Line = "Скачай новую версию, чтобы войти в игру.";
                s.Icon = "alert";
                s.Tone = Tone.Bad;
                s.Action = "Скачать";
                s.ActionIcon = "download";
                s.ActionPrimary = true;
                break;
            case SyncState.Setup:
                s.Title = "Установить игру";
                s.Icon = "download";
                s.PathText = gameDir;
                s.FolderLink = "Сменить папку";
                s.Right = Needs(sync.NeedBytes, sync.FreeBytes);
                s.Action = "Начать загрузку";
                s.ActionIcon = "download";
                s.ActionPrimary = true;
                break;
            case SyncState.Scanning:
                s.Title = "Проверка файлов";
                s.Icon = "retry";
                s.Track = true;
                // By files, as the line counts them: by bytes the bar stood at
                // a third with half the files done, the small ones being most.
                s.Progress = fileTotal > 0 ? (double)files / fileTotal : part;
                // Time left from the bytes hashed over the last few seconds;
                // until there is a rate to go by, the concept's own words.
                double rate = Speed(done);
                if (rate > 0 && done > 0)
                    s.Right = About((total - done) / rate);
                else
                    s.Right = "Это займёт немного времени";
                s.Line = "Проверено " + Count(files) + " из " + Count(fileTotal) + " файлов";
                break;
            case SyncState.Downloading:
                s.Track = true;
                s.Progress = total > 0 ? part : (fileTotal > 0 ? (double)files / fileTotal : 0);
                s.Icon = "download";
                if (!sync.Fresh && total < BIG_UPDATE)
                {
                    // A few files behind: no pause, no gigabytes.
                    int n = fileTotal;
                    s.Title = Theme.Plural(n, "Обновляется ", "Обновляются ", "Обновляется ") + n + " " +
                              Theme.Plural(n, "файл", "файла", "файлов");
                    s.Line = OfTotal(done, total);
                    s.Right = "Несколько секунд";
                }
                else
                {
                    // An install, or an update the size of one (a new
                    // folder over an old copy, files the check found broken):
                    // speed, time left and a pause, as the install has.
                    s.Title = "Загрузка игры";
                    double speed = Speed(done);
                    long left = Math.Max(0, total - done);
                    string tail = altPhase && speed > 0
                        ? About(left / speed)
                        : Theme.Size((long)speed) + "/с";
                    s.Line = "Загрузка: " + Theme.Size(left) + " осталось (" + tail + ")";
                    s.Right = Percent(done, total);
                    s.Action = "Приостановить";
                    s.ActionIcon = "pause";
                }
                break;
            case SyncState.Paused:
                s.Title = "Загрузка приостановлена";
                s.Icon = "pause";
                s.Tone = Tone.Paused;
                s.Track = true;
                s.Progress = part;
                s.Line = "Загрузка: " + Theme.Size(Math.Max(0, total - done)) + " осталось (пауза)";
                s.Right = Percent(done, total);
                s.Action = "Продолжить";
                s.ActionIcon = "play";
                break;
            case SyncState.NoSpace:
                s.Title = "Не хватает места на диске";
                s.Icon = "alert";
                s.Tone = Tone.Bad;
                s.Line = Needs(sync.NeedBytes, sync.FreeBytes);
                s.Action = "Сменить папку";
                s.ActionIcon = "arrow";
                break;
            case SyncState.Failed:
                s.Icon = "alert";
                s.Tone = Tone.Bad;
                switch (sync.Failure)
                {
                    case SyncFailure.Network:
                        s.Title = "Нет сети. Загрузка прервалась";
                        s.Line = "Проверь подключение к интернету";
                        if (done > 0)
                        {
                            s.Track = true;
                            s.Progress = part;
                            s.Right = "Скачанные файлы сохранены";
                        }
                        s.Action = "Повторить";
                        s.ActionIcon = "retry";
                        break;
                    case SyncFailure.Corrupt:
                        s.Title = "Файл не прошёл проверку";
                        s.Line = "Проверь файлы игры, чтобы загрузить повреждённый заново";
                        s.Action = "Проверить файлы";
                        s.ActionIcon = "retry";
                        break;
                    default:
                        s.Title = "Не удалось установить или обновить игру";
                        s.Line = sync.Note;
                        s.Action = "Повторить";
                        s.ActionIcon = "retry";
                        break;
                }
                break;
            case SyncState.Offline:
                // The published release was not taken, for one of four
                // reasons; the game here is whole either way, so the way in
                // stays open and the reason is the title.
                switch (sync.Cause)
                {
                    case OfflineCause.Unreachable:
                        s.Title = "Сервер обновлений не ответил";
                        s.Line = "Можно играть на своей копии игры";
                        break;
                    case OfflineCause.Refused:
                        s.Title = "Обновление не прошло проверку";
                        s.Line = "Можно играть на установленной версии";
                        break;
                    case OfflineCause.Download:
                        s.Title = "Не удалось скачать обновление";
                        s.Line = "Можно играть. При следующем запуске попробуем снова";
                        break;
                    default:
                        s.Title = "Не удалось обновить лаунчер";
                        s.Line = "Можно играть. Скачай новую версию лаунчера с сайта";
                        break;
                }
                s.Icon = "alert";
                s.Version = true;
                break;
            default:       // Ready
                s.Title = "Установлена актуальная версия игры";
                s.Icon = "check";
                s.Tone = Tone.Good;
                s.Version = true;
                break;
        }
        return s;
    }

    // Download speed over the last few seconds, from the byte count Sync
    // reports: (time, bytes) samples, the oldest dropped after four seconds.
    static readonly Queue<KeyValuePair<int, long>> samples = new Queue<KeyValuePair<int, long>>();
    static double speed;

    // A time left, the way the download line says it: "около 2 мин", and
    // under a minute "около 40 с", to five seconds.
    static string About(double seconds)
    {
        if (seconds > 55) return "около " + Math.Max(1, (long)Math.Round(seconds / 60)) + " мин";
        return "около " + Math.Max(5, (long)Math.Ceiling(seconds / 5) * 5) + " с";
    }

    static double Speed(long done)
    {
        int now = Environment.TickCount;
        if (samples.Count > 0 && done < samples.Peek().Value) samples.Clear();
        samples.Enqueue(new KeyValuePair<int, long>(now, done));
        while (samples.Count > 2 && now - samples.Peek().Key > 4000) samples.Dequeue();
        KeyValuePair<int, long> first = samples.Peek();
        if (now - first.Key > 500) speed = (done - first.Value) * 1000.0 / (now - first.Key);
        return speed;
    }

    // --- the account ----------------------------------------------------------

    static void Submit(string login, string password, bool remember)
    {
        if (busy || signedIn) return;
        busy = true;
        Render();

        Start(delegate
        {
            // A remembered account is remembered by its digest -- that is the
            // whole credential, and the password it came from is not kept
            // anywhere. So an untouched password box on the remembered login
            // means: use what we have.
            string h;
            if (form.Auth.PasswordRemembered && savedHash != null &&
                string.Equals(login, savedLogin, StringComparison.OrdinalIgnoreCase))
                h = savedHash;
            else
                h = Creds.Hash(password, login);

            Pers[] chars;
            Verdict v = GameProbe.Check(HOST, PORT, h, out chars);
            Say(delegate
            {
                busy = false;
                if (v != Verdict.Ok)
                {
                    form.Auth.Hint(Explain(v), true);
                    if (v == Verdict.Unreachable) serverUp = false;
                    Render();
                    return;
                }
                string name = chars.Length > 0 ? chars[0].Name : login;
                if (remember) Creds.Save(login, h, name);
                else Creds.Forget();
                Prefs.Set(Prefs.SignedOut, null);
                savedLogin = login;
                savedHash = h;
                savedName = name;
                hash = h;
                who = name;
                signedIn = true;
                serverUp = true;
                launchError = null;
                Card(chars);
                Render();
            });
        });
    }

    // The card: the first character's name, level and the place it comes
    // back to, named as the minimap names it; the level written the way the
    // concept writes it. A place too long for the card scrolls under the
    // pointer (AuthPanel).
    static void Card(Pers[] chars)
    {
        Pers c = chars.Length > 0 ? chars[0] : null;
        form.Auth.ShowAccount(who, c != null && c.Level > 0 ? "Уровень " + c.Level : "",
                              c != null ? c.Place : "");
    }

    static string Explain(Verdict v)
    {
        switch (v)
        {
            case Verdict.BadCredentials: return "Неверный логин или пароль";
            case Verdict.Banned: return "Учётная запись заблокирована";
            case Verdict.Unreachable: return "Сервер не отвечает. Попробуй позже.";
            default: return "Сервер ответил неожиданно";
        }
    }

    // The remembered account, asked about again in the background: the name
    // on the card may have changed, and a password changed by the
    // administrator is found out here rather than at "ИГРАТЬ".
    static void Recheck()
    {
        string h = hash;
        Pers[] chars;
        Verdict v = GameProbe.Check(HOST, PORT, h, out chars);
        Say(delegate
        {
            if (!signedIn || hash != h) return;
            switch (v)
            {
                case Verdict.Ok:
                    serverUp = true;
                    if (chars.Length > 0 && chars[0].Name != who)
                    {
                        who = chars[0].Name;
                        savedName = who;
                        Creds.Save(savedLogin, savedHash, who);
                    }
                    Card(chars);
                    break;
                case Verdict.BadCredentials:
                case Verdict.Banned:
                    Creds.Forget();
                    signedIn = false;
                    hash = null;
                    form.Auth.ShowLogin();
                    form.Auth.Fill(savedLogin, true);
                    form.Auth.Pass.Value = "";
                    form.Auth.Hint(Explain(v), true);
                    break;
                case Verdict.Unreachable:
                    serverUp = false;
                    break;
            }
            Render();
        });
    }

    // "Выйти". With "Запомнить меня" on, the account stays remembered: the
    // form comes back with the name and "Пароль сохранён", and the next start
    // shows it too instead of the card. With it off, nothing is kept.
    static void Logout()
    {
        if (launching) return;
        string h, n;
        bool kept = Creds.Load(out h, out n) != null && savedHash != null;
        signedIn = false;
        hash = null;
        who = "";
        form.Auth.ShowLogin();
        if (kept)
        {
            Prefs.Set(Prefs.SignedOut, "1");
            form.Auth.Fill(savedLogin, true);
        }
        else
        {
            Creds.Forget();
            savedHash = null;
            savedName = null;
            form.Auth.Fill(savedLogin, false);
            form.Auth.Pass.Value = "";
        }
        form.Auth.Login.Box.Focus();
        Render();
    }

    // --- background work ------------------------------------------------------

    // Unpacking 16 MB, asking the server whether it is up and checking the
    // release all happen while the player is still reading the window.
    static void Background()
    {
        Start(delegate
        {
            try { player = Unpack(); }
            catch (Exception e)
            {
                Say(delegate { launchError = "Не удалось распаковать проигрыватель: " + e.Message; Render(); });
            }
            playerReady.Set();
        });

        Start(delegate
        {
            bool up = GameProbe.Ping(HOST, PORT);
            Say(delegate
            {
                // A probe that got through on the account's own check has
                // the better evidence, so a failed ping does not undo it.
                if (serverUp != true || !up) serverUp = up;
                Render();
            });
        });

        if (signedIn) Start(Recheck);

        // The release check runs beside those, and unlike them it owns the
        // way in: until every file of the game is the published one,
        // "ИГРАТЬ" stays grey. Sync.Start returns at once and works on its
        // own thread, so this costs the window nothing.
        sync.Changed = delegate { Say(Render); };
        sync.Start();

        // The download line alternates speed and time left every three
        // seconds, as the concept does.
        System.Windows.Forms.Timer t = new System.Windows.Forms.Timer();
        t.Interval = 3000;
        t.Tick += delegate
        {
            altPhase = !altPhase;
            if (sync.State == SyncState.Downloading) Render();
        };
        t.Start();
    }

    static bool altPhase;

    // The panel's button, in every state but "ИГРАТЬ".
    static void PanelAction()
    {
        switch (sync.State)
        {
            case SyncState.MustUpdate:
                Browse(sync.ManualUrl);
                break;
            case SyncState.Setup:
                sync.Begin();
                break;
            case SyncState.Downloading:
                sync.Pause();
                break;
            case SyncState.Paused:
                sync.Start();
                break;
            case SyncState.NoSpace:
                PickFolder();
                break;
            case SyncState.Failed:
                if (sync.Failure == SyncFailure.Corrupt) Verify();
                else sync.Start();
                break;
        }
        Render();
    }

    // Start this exe again and go: after a self-update (the new exe already
    // has this one's name) or after the game folder changed. The lock is let
    // go first so the new one does not wait it out.
    static void Restart(string arg)
    {
        if (Interlocked.Exchange(ref restarting, 1) != 0) return;
        try
        {
            Process.Start(new ProcessStartInfo(exe, arg ?? "") { UseShellExecute = false, WorkingDirectory = here });
        }
        catch (Exception e)
        {
            Notice.Show("Лаунчер обновлён", "Запустите его ещё раз: " + e.Message);
        }
        try { single.ReleaseMutex(); } catch { }
        Environment.Exit(0);
    }

    // --- starting the game ------------------------------------------------------

    static void Play()
    {
        if (!form.Panel.CanPlay || launching) return;
        // The second lock on the same door, for the day somebody wires up
        // another way in. Pressed during the quiet check, the game starts
        // once the check is over, if the release is still playable.
        bool wait = quiet && !sync.Playable;
        if (!sync.Playable && !wait) return;
        launching = true;
        launchError = null;
        Render();
        string h = hash;

        Start(delegate
        {
            if (wait)
            {
                sync.Wait(Timeout.Infinite);
                if (!sync.Playable)
                {
                    Say(delegate { launching = false; Render(); });
                    return;
                }
            }
            playerReady.WaitOne();
            if (player == null)
            {
                Say(delegate { launching = false; Render(); });
                return;
            }
            try { LaunchWeb(h); }
            catch (Exception e)
            {
                // Let the door open again. launched is a guard against two
                // clicks landing together, not a one-shot fuse: if the
                // projector could not be started -- an antivirus took the
                // unpacked player, the disk filled -- the player has to be
                // able to try again without closing the launcher.
                Interlocked.Exchange(ref launched, 0);
                Say(delegate
                {
                    launching = false;
                    launchError = "Не удалось запустить игру: " + e.Message;
                    Render();
                });
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
        // The projector opens its window on screen, white and unpainted,
        // before it gets round to the request that parks it (measured: some
        // 400 ms in which SetWindowPos waits on its thread). The screen as it
        // is lies over everything until the window is away.
        Cover cover = null;
        form.Invoke((MethodInvoker)delegate { cover = Cover.Lay(); });
        Start(delegate { Thread.Sleep(5000); Say(cover.Lift); });
        Process game;
        try
        {
            game = Process.Start(new ProcessStartInfo(player, "\"" + server.MovieUrl() + "\"")
            {
                UseShellExecute = false,
                WindowStyle = ProcessWindowStyle.Hidden,
                WorkingDirectory = here,
            });
        }
        catch
        {
            Say(cover.Lift);
            throw;
        }
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
            Say(cover.Lift);
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
            LocalServer s = server;
            if (s != null) s.Stop();
            Say(Back);
        });

        Say(delegate
        {
            Render();
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
            LocalServer s = server;
            if (s == null || Environment.TickCount - s.LastRequest > 600) break;
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

    const int REVEAL_DRAW_MS = 350;       // the game's first frames on screen, under the still

    static void Done()
    {
        if (gameProc == null) return;   // the game has already come and gone
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
            // Flash does not draw a window that is off screen, so the game
            // arrives on screen unpainted and for a frame the area round the
            // launcher is white (caught on a 60 fps recording). So the screen
            // as it is, launcher and all, lies over everything while the game
            // comes on screen and draws, and the launcher goes and the still
            // lifts in one step: the launcher simply turns into the game.
            Cover cover = null;
            try { form.Invoke((MethodInvoker)delegate { cover = Cover.Lay(); }); } catch { }
            lock (windowLock)
            {
                if (gameWnd == IntPtr.Zero) gameWnd = h;
                GameWindow.Reveal(gameWnd);
            }
            Thread.Sleep(REVEAL_DRAW_MS);
            Say(delegate
            {
                inGame = true;
                TrayText();
                form.Hide();
                if (cover != null) cover.Lift();
            });
        });
    }

    // The game has closed. The launcher comes back as it was left, with the
    // account still signed in, and looks for an update at once: anything
    // published while the game ran is taken now rather than on the next start.
    static void Back()
    {
        lock (windowLock)
        {
            revealed = false;
            gameWnd = IntPtr.Zero;
        }
        gameProc = null;
        server = null;
        Interlocked.Exchange(ref launched, 0);
        launching = false;
        inGame = false;
        TrayText();
        form.Back();
        quiet = true;
        sync.Start();
        // A session moves the character on: a new level, another place.
        if (signedIn) Start(Recheck);
        Render();
    }
    // The launcher sits in the tray for as long as it is open. A click
    // brings up the game while it runs and the launcher otherwise; the menu
    // has both, and closing the game or, with no game, the launcher.
    static NotifyIcon tray;
    static bool inGame;                   // the world is on screen; the launcher stepped aside
    static bool quiet;                    // the check after a game, not shown unless it finds something

    static void TrayOn()
    {
        tray = new NotifyIcon();
        tray.Icon = Brand.AppIcon();
        tray.MouseClick += delegate (object o, MouseEventArgs e)
        {
            if (e.Button != MouseButtons.Left) return;
            if (inGame) RaiseGame(); else ShowLauncher();
        };
        ContextMenuStrip menu = new ContextMenuStrip();
        // Built as it opens: what it offers depends on whether a game runs.
        menu.Opening += delegate
        {
            menu.Items.Clear();
            menu.Items.Add("Открыть лаунчер", null, delegate { ShowLauncher(); });
            if (inGame)
            {
                menu.Items.Add("Показать игру", null, delegate { RaiseGame(); });
                menu.Items.Add("Закрыть игру", null, delegate { CloseGame(); });
            }
            else if (!launching)
            {
                menu.Items.Add("Проверить обновления", null, delegate { CheckNow(); });
                menu.Items.Add("Закрыть лаунчер", null, delegate { Environment.Exit(0); });
            }
        };
        menu.Items.Add("");               // so that Opening fires; replaced at once
        tray.ContextMenuStrip = menu;
        TrayText();
        tray.Visible = true;
        // Whatever way the process ends, the icon goes with it rather than
        // linger in the tray until the pointer passes over it.
        AppDomain.CurrentDomain.ProcessExit += delegate
        {
            try { tray.Visible = false; } catch { }
        };
    }

    static void TrayText()
    {
        if (tray != null) tray.Text = inGame ? "LAVA Reborn: игра запущена" : "LAVA Reborn";
    }

    // From the tray, also while the game runs: then the panel says so and
    // the way in is shut until the game closes.
    static void ShowLauncher()
    {
        form.Reveal();
        Render();
    }
    static void RaiseGame()
    {
        IntPtr h;
        lock (windowLock) h = gameWnd;
        GameWindow.Raise(h);
    }

    // As its own close box would; one that does not go in three seconds is
    // ended. Either way the thread waiting on it brings the launcher back.
    static void CloseGame()
    {
        Process p = gameProc;
        if (p == null) return;
        IntPtr h;
        lock (windowLock) h = gameWnd;
        GameWindow.Close(h);
        Start(delegate
        {
            try { if (!p.WaitForExit(3000)) p.Kill(); } catch { }
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

    // --- looking at the design ----------------------------------------------
    //
    // LAVA_PANEL=<state> pins the resource panel to one of the concept's
    // states -- setup, download, paused, update, checking, ready, outdated,
    // offline, network, disk, corrupt -- with the concept's own figures, so
    // the drawing can be set against the mock-up's screenshots. Nothing else
    // in the window is affected.
    static PanelState Preview()
    {
        string want = Environment.GetEnvironmentVariable("LAVA_PANEL");
        if (string.IsNullOrEmpty(want)) return null;
        PanelState s = new PanelState();
        switch (want.Trim().ToLowerInvariant())
        {
            case "setup":
                s.Title = "Установить игру"; s.Icon = "download";
                s.PathText = @"D:\Games\LAVA Reborn"; s.FolderLink = "Сменить папку";
                s.Right = "Нужно 2,5 ГБ · Свободно 18,6 ГБ";
                s.Action = "Начать загрузку"; s.ActionIcon = "download"; s.ActionPrimary = true;
                break;
            case "download":
                s.Title = "Загрузка игры"; s.Icon = "download"; s.Track = true; s.Progress = 0.64;
                s.Line = "Загрузка: 0,8 ГБ осталось (12,8 МБ/с)"; s.Right = "64 %";
                s.Action = "Приостановить"; s.ActionIcon = "pause";
                break;
            case "paused":
                s.Title = "Загрузка приостановлена"; s.Icon = "pause"; s.Tone = Tone.Paused;
                s.Track = true; s.Progress = 0.64;
                s.Line = "Загрузка: 0,8 ГБ осталось (пауза)"; s.Right = "64 %";
                s.Action = "Продолжить"; s.ActionIcon = "play";
                break;
            case "update":
                s.Title = "Обновляется 6 файлов"; s.Icon = "download"; s.Track = true; s.Progress = 0.48;
                s.Line = "1,1 из 2,3 МБ"; s.Right = "Несколько секунд";
                break;
            case "checking":
                s.Title = "Проверка файлов"; s.Icon = "retry"; s.Track = true; s.Progress = 0.42;
                s.Line = "Проверено 10 920 из 26 000 файлов"; s.Right = "Это займёт немного времени";
                break;
            case "outdated":
                s.Title = "Лаунчер устарел"; s.Icon = "alert"; s.Tone = Tone.Bad;
                s.Line = "Скачай новую версию, чтобы войти в игру.";
                s.Action = "Скачать"; s.ActionIcon = "download"; s.ActionPrimary = true;
                break;
            case "network":
                s.Title = "Нет сети. Загрузка прервалась"; s.Icon = "alert"; s.Tone = Tone.Bad;
                s.Track = true; s.Progress = 0.64;
                s.Line = "Проверь подключение к интернету"; s.Right = "Скачанные файлы сохранены";
                s.Action = "Повторить"; s.ActionIcon = "retry";
                break;
            case "disk":
                s.Title = "Не хватает места на диске"; s.Icon = "alert"; s.Tone = Tone.Bad;
                s.Line = "Нужно 2,5 ГБ · Свободно 640 МБ";
                s.Action = "Сменить папку"; s.ActionIcon = "arrow";
                break;
            case "corrupt":
                s.Title = "Файл не прошёл проверку"; s.Icon = "alert"; s.Tone = Tone.Bad;
                s.Line = "Проверь файлы игры, чтобы загрузить повреждённый заново";
                s.Action = "Проверить файлы"; s.ActionIcon = "retry";
                break;
            default:   // ready, offline
                s.Title = "Установлена актуальная версия игры"; s.Icon = "check"; s.Tone = Tone.Good;
                s.Version = true;
                break;
        }
        return s;
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

    static Image LoadImage(string name)
    {
        try
        {
            using (Stream s = Open(name))
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
            string line = gameDir.TrimEnd('\\');
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
                "\n\nи впишите в него одну строку: путь к этой папке:\n\n" + gameDir);
        }
    }
}
