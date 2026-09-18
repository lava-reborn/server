// One file a player double-clicks, beside their own res/ folder.
//
// It carries the two things that are not part of the game -- the Flash
// projector and the string table we generate -- and it does the three chores
// that otherwise fall to the player: unpack the projector, put texts.xml
// where the client looks for it, and add the folder to Flash's trust list so
// the sandbox will let the game open a socket at all.
//
// The client itself is not embedded and never distributed: it stays the
// player's own copy in res/. main.swf is not written to either -- the only
// thing added beside it is main1280x720.swf, the same movie with a 16:9
// stage instead of the shipped 950x650 one. Delete it and the next start
// makes it again; delete this launcher and the original is exactly as it was.
//
// Built by launcher/build.ps1 with csc.exe out of the Windows .NET Framework,
// so there is nothing to install to produce it.
using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
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

        // 16:9. The shipped movie has a 950x650 stage and the client never
        // sets a scale mode, so a wider window only zooms it and leaves bars
        // down the sides. The client itself is ready for more -- SceneShifter
        // keeps minW 950 / minH 650 against maxW 1280 / maxH 1024 and lays
        // itself out from Stage.width -- so the stage is what has to change.
        //
        // main.swf is not touched: the widescreen stage goes into a copy
        // beside it, which is also why it has to live in res/ (the client
        // loads every asset relative to its own file).
        string movie = Widescreen(here, main);
        string url = movie + "?vversion=1&var_host=" + HOST + "&var_port=" + PORT;
        Process game = Process.Start(new ProcessStartInfo(player, "\"" + url + "\"")
        {
            UseShellExecute = false,
            WorkingDirectory = here,
        });
        Rename(game);
        return 0;
    }

    // --- the widescreen copy ---------------------------------------------

    // What the client was built for, and the ceiling its own layout obeys.
    const int BASE_W = 1280, BASE_H = 1024;

    // 1280x720 and not the monitor's own size, which was tried and does not
    // work: raising the ceiling to 2560x1440 does make the client lay itself
    // out that large, and the interface comes apart doing it -- the panels
    // walk off the edges and the frame around the view disappears. The art
    // was drawn for a window this big and no bigger, so the stage matches the
    // ceiling and the projector magnifies from there.
    static void Target(out int wide, out int high)
    {
        wide = 1280;
        high = 720;
    }

    static string Widescreen(string here, string main)
    {
        int WIDE, HIGH;
        Target(out WIDE, out HIGH);
        // The size is in the name, so a monitor change makes a new file
        // instead of quietly reusing one built for the old one.
        string wide = Path.Combine(here, "res",
                                   string.Format("main{0}x{1}.swf", WIDE, HIGH));
        try
        {
            if (File.Exists(wide) &&
                File.GetLastWriteTimeUtc(wide) >= File.GetLastWriteTimeUtc(main))
                return wide;

            byte[] raw = File.ReadAllBytes(main);
            byte[] body;
            if (raw[0] == 'C')
            {
                // CWS is zlib: an 8-byte SWF header, then a 2-byte zlib
                // header, then raw deflate. .NET 4 has no zlib stream, so the
                // two bytes are skipped and the deflate read directly.
                using (var src = new MemoryStream(raw, 10, raw.Length - 10))
                using (var inf = new DeflateStream(src, CompressionMode.Decompress))
                using (var dst = new MemoryStream())
                {
                    inf.CopyTo(dst);
                    body = dst.ToArray();
                }
            }
            else if (raw[0] == 'F')
            {
                body = new byte[raw.Length - 8];
                Array.Copy(raw, 8, body, 0, body.Length);
            }
            else
            {
                return main;             // ZWS, or not a movie at all
            }

            body = WithStage(body, WIDE, HIGH);
            if (body == null)
                return main;

            // Written back uncompressed, which the player reads just as
            // happily: it costs a few megabytes of disk and saves carrying a
            // zlib compressor in here. The length field of the header is the
            // uncompressed size either way, so it is already right.
            byte[] head = new byte[8];
            Array.Copy(raw, head, 8);
            head[0] = (byte)'F';
            // The length field is the uncompressed size, and the rebuilt
            // rectangle may be a byte or two longer than the old one.
            Array.Copy(BitConverter.GetBytes(body.Length + 8), 0, head, 4, 4);
            using (var fs = File.Create(wide))
            {
                fs.Write(head, 0, 8);
                fs.Write(body, 0, body.Length);
            }
            return wide;
        }
        catch
        {
            // A 950x650 game is a working game. Nothing here is worth
            // refusing to start over.
            return main;
        }
    }

    // The stage is the first thing in the movie after the header: a RECT of
    // four signed values in twips, packed into a bit field whose width is in
    // the top five bits. The shipped one uses 16 bits a value, which tops out
    // at 32767 twips -- 1638 pixels -- so anything wider than that needs the
    // field itself to grow. The RECT is the first thing in the body and
    // nothing after it refers to an offset, so it can simply be rebuilt and
    // the rest appended unchanged.
    static byte[] WithStage(byte[] body, int wide, int high)
    {
        int nbits = body[0] >> 3;
        if (nbits < 2 || nbits > 31)
            return null;
        int oldBytes = (5 + 4 * nbits + 7) / 8;
        if (oldBytes > body.Length)
            return null;

        int[] want = { 0, wide * 20, 0, high * 20 };
        int need = 2;                       // one for the sign, one for a bit
        foreach (int v in want)
        {
            int bits = 1;                   // the sign
            for (int m = v; m != 0; m >>= 1)
                bits++;
            if (bits > need)
                need = bits;
        }
        if (need > 31)
            return null;

        int newBytes = (5 + 4 * need + 7) / 8;
        var flags = new bool[newBytes * 8];
        int pos = 0;
        for (int b = 4; b >= 0; b--)
            flags[pos++] = ((need >> b) & 1) != 0;
        foreach (int v in want)
            for (int b = need - 1; b >= 0; b--)
                flags[pos++] = ((v >> b) & 1) != 0;

        var rect = new byte[newBytes];
        for (int i = 0; i < newBytes; i++)
        {
            int v = 0;
            for (int b = 0; b < 8; b++)
                v = (v << 1) | (flags[i * 8 + b] ? 1 : 0);
            rect[i] = (byte)v;
        }

        var outBody = new byte[rect.Length + body.Length - oldBytes];
        Array.Copy(rect, 0, outBody, 0, rect.Length);
        Array.Copy(body, oldBytes, outBody, rect.Length, body.Length - oldBytes);
        return outBody;
    }

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
