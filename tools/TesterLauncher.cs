// Local tester mode using the production launcher's theme and embedded artwork.
// No updater, production credentials or remote game endpoint are used here.
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static class TesterLauncher
{
    internal sealed class StartupReport
    {
        public int Ready, Progress;
        public string Stage, Instance;
    }

    static Form window;
    static Label status, detail;
    static Button play;
    static Meter progress;
    static Process backend, game;
    static System.Windows.Forms.Timer timer;
    static string root, instance;
    static bool ready, polling, failed;
    static volatile bool closing;
    static readonly Stopwatch startup = new Stopwatch();

    [STAThread]
    static void Main()
    {
        Theme.OverImage = false;
        Application.EnableVisualStyles();
        Application.SetCompatibleTextRenderingDefault(false);
        root = Path.GetDirectoryName(Application.ExecutablePath);
        string id;
        using (SHA256 sha = SHA256.Create())
            id = BitConverter.ToString(sha.ComputeHash(
                Encoding.UTF8.GetBytes(root.ToLowerInvariant())))
                .Replace("-", "").Substring(0, 24);
        bool owner;
        using (Mutex single = new Mutex(true, "Local\\LavaTester_" + id, out owner))
        {
            if (!owner)
            {
                MessageBox.Show("Тестовый лаунчер этой папки уже открыт.", "Lava Reborn");
                return;
            }
            try { Run(); }
            catch (Exception error)
            {
                MessageBox.Show(error.Message, "Не удалось запустить тестовый комплект",
                    MessageBoxButtons.OK, MessageBoxIcon.Error);
            }
        }
    }

    static Image Artwork(string name)
    {
        using (Stream stream = Assembly.GetExecutingAssembly().GetManifestResourceStream(name))
        using (Image original = Image.FromStream(stream))
            return new Bitmap(original);
    }

    static Button AddButton(string text, int x, int width)
    {
        Button button = new Button {
            Text = text, Left = x, Top = 540, Width = width, Height = 42,
            FlatStyle = FlatStyle.Flat, BackColor = Theme.BtnBg, ForeColor = Theme.BtnInk
        };
        button.FlatAppearance.BorderColor = Theme.BtnLine;
        window.Controls.Add(button);
        return button;
    }

    static void Run()
    {
        foreach (string file in new[] {
            "python\\pythonw.exe", "python\\python.exe", "player\\flashplayer_32_sa.exe",
            "state\\tester.sqlite", "start.py"
        })
            if (!File.Exists(Path.Combine(root, file)))
                throw new IOException("Не найден файл " + file + ". Распакуйте весь тестовый комплект.");
        using (Image photo = Artwork("hero"))
        using (Image logo = Artwork("logo"))
        using (Form form = new Form {
            Text = "Lava Reborn — локальный тест", ClientSize = new Size(1120, 606),
            StartPosition = FormStartPosition.CenterScreen,
            FormBorderStyle = FormBorderStyle.FixedSingle, MaximizeBox = false,
            BackColor = Theme.Bg, ForeColor = Theme.Ink, Font = new Font("Segoe UI", 10)
        })
        {
            window = form;
            window.Icon = Icon.ExtractAssociatedIcon(Application.ExecutablePath);
            PictureBox hero = new PictureBox {
                Left = 1, Top = 1, Width = 778, Height = 448,
                Image = photo, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Theme.BgHero
            };
            hero.Controls.Add(new PictureBox {
                Left = 24, Top = 20, Width = 300, Height = 100,
                Image = logo, SizeMode = PictureBoxSizeMode.Zoom, BackColor = Color.Transparent
            });
            window.Controls.Add(hero);
            window.Controls.Add(new Label {
                Text = "ЛОКАЛЬНЫЙ ТЕСТ", Left = 805, Top = 36, Width = 285, Height = 32,
                ForeColor = Theme.Accent, Font = new Font("Segoe UI", 14, FontStyle.Bold)
            });
            detail = new Label {
                Text = "Подготавливаем ресурсы игры. Дождитесь завершения, затем нажмите «Играть».\n\n" +
                       "После закрытия игры лаунчер сохранит серверы для быстрого повторного входа.",
                Left = 805, Top = 100, Width = 285, Height = 260,
                ForeColor = Theme.InkMuted
            };
            status = new Label {
                Text = "Запуск локальных серверов…", Left = 24, Top = 467,
                Width = 1072, Height = 28
            };
            progress = new Meter { Left = 24, Top = 503, Width = 1072, Height = 10 };
            window.Controls.Add(detail);
            window.Controls.Add(status);
            window.Controls.Add(progress);
            play = AddButton("Играть", 24, 280);
            play.BackColor = Theme.Accent;
            play.ForeColor = Theme.OnAccent;
            play.Enabled = false;
            play.Click += delegate { Play(); };
            AddButton("Аккаунты", 324, 240).Click += delegate {
                try
                {
                    Process.Start(new ProcessStartInfo("notepad.exe",
                        "\"" + Path.Combine(root, "accounts.csv") + "\"") { UseShellExecute = false });
                }
                catch (Win32Exception error) { status.Text = error.Message; }
            };
            AddButton("Остановить и выйти", 804, 292).Click += delegate { window.Close(); };
            window.Shown += delegate { StartBackend(); };
            window.FormClosing += Closing;
            try { Application.Run(window); }
            finally
            {
                if (timer != null) timer.Dispose();
                if (backend != null)
                {
                    try { backend.StandardInput.Close(); } // EOF asks the backend to stop.
                    catch (IOException) { }
                    backend.Dispose();
                }
                if (game != null) game.Dispose();
            }
        }
    }

    static void StartBackend()
    {
        try
        {
            instance = Guid.NewGuid().ToString("N");
            ProcessStartInfo info = new ProcessStartInfo(Path.Combine(root, "python\\pythonw.exe"),
                "-B \"" + Path.Combine(root, "start.py") + "\" --backend --instance " + instance) {
                WorkingDirectory = root, UseShellExecute = false,
                CreateNoWindow = true, RedirectStandardInput = true
            };
            info.EnvironmentVariables["PYTHONHOME"] = "";
            info.EnvironmentVariables["PYTHONPATH"] = "";
            backend = Process.Start(info);
            startup.Restart();
            timer = new System.Windows.Forms.Timer { Interval = 500 };
            timer.Tick += delegate { Tick(); };
            timer.Start();
        }
        catch (Win32Exception error) { Fail(error.Message); }
    }

    static void Fail(string message)
    {
        failed = true;
        play.Enabled = false;
        status.ForeColor = Theme.Red;
        status.Text = message;
    }

    internal static StartupReport DecodeStatus(string response)
    {
        StartupReport report = new StartupReport { Ready = -2, Progress = -1 };
        foreach (string field in response.Split('&'))
        {
            string[] pair = field.Split(new[] { '=' }, 2);
            if (pair.Length != 2) continue;
            string value = Uri.UnescapeDataString(pair[1].Replace("+", " "));
            int number;
            if (pair[0] == "ready" && Int32.TryParse(value, out number)) report.Ready = number;
            if (pair[0] == "progress" && Int32.TryParse(value, out number)) report.Progress = number;
            if (pair[0] == "stage") report.Stage = value;
            if (pair[0] == "instance") report.Instance = value;
        }
        if (report.Ready < -1 || report.Ready > 1 || report.Progress < 0 ||
            report.Progress > 100 || String.IsNullOrWhiteSpace(report.Stage))
            throw new FormatException("Некорректный статус локального сервера.");
        return report;
    }

    internal static bool Owns(StartupReport report, string expected)
    {
        return !String.IsNullOrEmpty(expected) &&
            String.Equals(report.Instance, expected, StringComparison.Ordinal);
    }

    static void Tick()
    {
        if (closing) return;
        if (backend == null || backend.HasExited)
        {
            if (!failed) Fail("Локальный сервер остановлен. Подробности — в state/startup.log.");
            return;
        }
        if (game != null && game.HasExited)
        {
            game.Dispose();
            game = null;
            status.Text = "Клиент закрыт. Серверы готовы к повторному входу.";
        }
        // Preparation now finishes in the launcher, before Flash is opened.
        play.Enabled = ready && game == null && !failed;
        if (!ready && !failed && startup.Elapsed.TotalMinutes > 10)
            Fail("Подготовка затянулась. Подробности — в state/http.log.");
        if (ready || failed || polling) return;
        polling = true;
        ThreadPool.QueueUserWorkItem(delegate {
            StartupReport report = null;
            try
            {
                HttpWebRequest request = (HttpWebRequest)WebRequest.Create(
                    "http://127.0.0.1:18080/startup-status");
                request.Proxy = null;
                request.Timeout = 1500;
                request.ReadWriteTimeout = 1500;
                request.CachePolicy = new System.Net.Cache.RequestCachePolicy(
                    System.Net.Cache.RequestCacheLevel.NoCacheNoStore);
                using (WebResponse answer = request.GetResponse())
                using (StreamReader reader = new StreamReader(answer.GetResponseStream(), Encoding.UTF8))
                    report = DecodeStatus(reader.ReadToEnd());
            }
            catch (WebException) { }
            catch (IOException) { }
            catch (FormatException) { }
            if (closing || window.IsDisposed) return;
            try
            {
                window.BeginInvoke((Action)delegate {
                    polling = false;
                    if (closing || report == null || !Owns(report, instance)) return;
                    status.Text = report.Stage;
                    progress.Value = report.Progress;
                    if (report.Ready == -1) Fail(report.Stage);
                    if (report.Ready == 1)
                    {
                        ready = true;
                        status.Text = "Готово. Можно запускать игру.";
                        detail.Text = "Ресурсы подготовлены.\n\nЗакройте игру и снова нажмите «Играть» для повторного входа.\n\n" +
                                      "Чтобы остановить локальные серверы, закройте лаунчер.";
                        play.Enabled = game == null;
                    }
                });
            }
            catch (InvalidOperationException) { } // Window closed while request completed.
        });
    }

    static void Play()
    {
        if (!ready || failed || (game != null && !game.HasExited)) return;
        try
        {
            game = Process.Start(new ProcessStartInfo(Path.Combine(root, "player\\flashplayer_32_sa.exe"),
                "\"http://127.0.0.1:18080/res/main.swf?vversion=1\"") {
                WorkingDirectory = root, UseShellExecute = false
            });
            play.Enabled = false;
            status.Text = "Игра запущена.";
        }
        catch (Win32Exception error) { status.Text = "Не удалось открыть игру: " + error.Message; }
    }

    static void Closing(object sender, FormClosingEventArgs args)
    {
        if (closing) return;
        closing = true;
        if (game != null && !game.HasExited)
        {
            game.CloseMainWindow();
            if (!game.WaitForExit(3000))
            {
                closing = false;
                args.Cancel = true;
                MessageBox.Show("Сначала закройте окно игры, чтобы сохранить прогресс.");
                return;
            }
        }
        if (backend != null && !backend.HasExited)
        {
            try
            {
                backend.StandardInput.WriteLine("stop");
                backend.StandardInput.Flush();
            }
            catch (IOException) { }
            if (!backend.WaitForExit(10000))
            {
                closing = false;
                args.Cancel = true;
                MessageBox.Show("Сервер завершает работу. Попробуйте закрыть лаунчер ещё раз.");
                return;
            }
        }
        if (timer != null) timer.Stop();
    }

    sealed class Meter : Control
    {
        int value;
        public int Value
        {
            get { return value; }
            set { if (this.value != value) { this.value = value; Invalidate(); } }
        }
        public Meter()
        {
            SetStyle(ControlStyles.UserPaint | ControlStyles.AllPaintingInWmPaint |
                ControlStyles.OptimizedDoubleBuffer, true);
        }
        protected override void OnPaint(PaintEventArgs args)
        {
            args.Graphics.Clear(Theme.Track);
            using (SolidBrush brush = new SolidBrush(Theme.Accent))
                args.Graphics.FillRectangle(brush, 0, 0, Width * value / 100, Height);
        }
    }
}
