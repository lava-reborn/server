// One file a player double-clicks, beside their own res/ folder.
//
// It carries the two things that are not part of the game -- the Flash
// projector and the string table we generate -- and it does the three chores
// that otherwise fall to the player: unpack the projector, put texts.xml
// where the client looks for it, and add the folder to Flash's trust list so
// the sandbox will let the game open a socket at all.
//
// The client itself is not touched, not embedded and not modified. It stays
// the player's own copy in res/, which this only reads.
//
// Built by launcher/build.ps1 with csc.exe out of the Windows .NET Framework,
// so there is nothing to install to produce it.
using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static class Launcher
{
    // Filled in at build time by build.ps1 -Host -Port.
    const string HOST = "@HOST@";
    const string PORT = "@PORT@";
    const string TITLE = "LAVA Online";

    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetWindowText(IntPtr hWnd, string text);

    [STAThread]
    static int Main()
    {
        try
        {
            return Run();
        }
        catch (Exception e)
        {
            Fail("Не удалось запустить игру.\n\n" + e.Message);
            return 1;
        }
    }

    static int Run()
    {
        string here = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        string main = Path.Combine(here, "res", "main.swf");
        if (!File.Exists(main))
        {
            Fail("Рядом с этой программой нет папки res с игрой.\n\n" +
                 "Положите её туда же, где лежит этот файл, так чтобы\n" +
                 "получился путь:\n\n" + main + "\n\n" +
                 "Игра в раздачу не входит — это ваша собственная копия.");
            return 1;
        }

        // The string table the shipped client is missing. Without it the game
        // reaches the login window and then throws the player back to it the
        // moment the server names anything.
        string texts = Path.Combine(here, "res", "database", "texts.xml");
        if (!File.Exists(texts))
        {
            Directory.CreateDirectory(Path.GetDirectoryName(texts));
            Extract("texts.xml", texts);
        }

        Trust(here);

        // The projector is unpacked once and kept: it is 16 MB, and writing
        // it out on every start would be both slow and pointless. A size
        // mismatch means a half-written or older copy, so it is redone.
        string dir = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "LavaOnline");
        Directory.CreateDirectory(dir);
        string player = Path.Combine(dir, "flashplayer.exe");
        long want = Size("fp32_sa.exe");
        if (!File.Exists(player) || new FileInfo(player).Length != want)
            Extract("fp32_sa.exe", player);

        // No switch carries flashvars into the projector; they ride in the
        // query string of the movie's own path, and Flash unpacks them into
        // _root exactly as it would from a web page. var_host and var_port
        // are where the client reads the server's address in local mode.
        string url = main + "?vversion=1&var_host=" + HOST + "&var_port=" + PORT;
        Process game = Process.Start(new ProcessStartInfo(player, "\"" + url + "\"")
        {
            UseShellExecute = false,
            WorkingDirectory = here,
        });
        Rename(game);
        return 0;
    }

    // The projector titles its window after itself and offers no way to say
    // otherwise, so the name is set from out here once the window exists.
    // It is renamed more than once because the player writes the title again
    // during start-up, and a single early rename is simply overwritten.
    static void Rename(Process game)
    {
        try
        {
            IntPtr hwnd = IntPtr.Zero;
            for (int i = 0; i < 100 && hwnd == IntPtr.Zero; i++)
            {
                if (game.HasExited) return;
                Thread.Sleep(200);
                game.Refresh();
                hwnd = game.MainWindowHandle;
            }
            if (hwnd == IntPtr.Zero) return;

            for (int i = 0; i < 12; i++)
            {
                SetWindowText(hwnd, TITLE);
                Thread.Sleep(500);
                if (game.HasExited) return;
            }
        }
        catch
        {
            // A window with the wrong name above it is still a working game.
        }
    }

    // Flash will not open a socket for a movie loaded off the disk unless the
    // folder is trusted: without this the login window appears and the play
    // button answers that the connection was not established, while the
    // server never sees a byte. One line naming the folder is the remedy, and
    // it covers res/ underneath it.
    static void Trust(string here)
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
            else
            {
                File.WriteAllText(cfg, line + "\r\n", Encoding.Default);
            }
        }
        catch (Exception e)
        {
            // Not fatal on its own: the game still starts and still shows the
            // login window. It just will not connect, and a player told why
            // can fix it by hand.
            Fail("Не удалось разрешить игре выход в сеть.\n\n" + e.Message +
                 "\n\nИгра запустится, но соединение с сервером установить\n" +
                 "не сможет. Создайте вручную файл\n\n" +
                 @"%APPDATA%\Macromedia\Flash Player\#Security\FlashPlayerTrust\lava.cfg" +
                 "\n\nи впишите в него одну строку — путь к этой папке:\n\n" + here);
        }
    }

    static long Size(string name)
    {
        using (Stream s = Open(name)) return s.Length;
    }

    static void Extract(string name, string path)
    {
        using (Stream src = Open(name))
        using (FileStream dst = File.Create(path))
            src.CopyTo(dst);
    }

    static Stream Open(string name)
    {
        Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream(name);
        if (s == null)
            throw new InvalidOperationException(
                "В этой сборке нет вложенного файла " + name + ".");
        return s;
    }

    static void Fail(string message)
    {
        MessageBox.Show(message, "LAVA Online",
                        MessageBoxButtons.OK, MessageBoxIcon.Warning);
    }
}
