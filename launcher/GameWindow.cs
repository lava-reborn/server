// Keeping the game's window off screen until there is a world in it.
//
// The auto-login path builds the client's own login frame and only then
// connects: Session.attribsLoaded (Session.as:71-72) calls
// SceneShifter.enterScene() before connect(), and enterScene() is what
// attaches enterWinFrame. So the frame we went to all this trouble to skip is
// on screen anyway for as long as logging in and loading the first location
// takes -- a second or so, empty fields and all.
//
// It cannot be stopped from being drawn without touching the movie, so it is
// drawn somewhere nobody is looking. The projector is started hidden, its
// window is parked at -32000 the moment it exists, and it is made visible
// there -- visible, because a hidden or minimised window is what makes Flash
// throttle itself, and this one has loading to do. When the world is ready the
// window is moved back to the middle of the screen and raised.
using System;
using System.Diagnostics;
using System.Drawing;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

static class GameWindow
{
    const int SW_SHOWNOACTIVATE = 4, SW_SHOW = 5;
    const uint SWP_NOSIZE = 0x0001, SWP_NOZORDER = 0x0004, SWP_NOACTIVATE = 0x0010;
    const uint GW_OWNER = 4;
    const int PARKED = -32000;

    delegate bool EnumProc(IntPtr hwnd, IntPtr lparam);

    [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc cb, IntPtr lparam);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint pid);
    [DllImport("user32.dll")] static extern IntPtr GetWindow(IntPtr hwnd, uint cmd);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr hwnd, out RECT r);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr hwnd, out RECT r);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hwnd, int cmd);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr hwnd, IntPtr after,
                                                             int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool IsIconic(IntPtr hwnd);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr hwnd, uint msg, IntPtr w, IntPtr l);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetWindowText(IntPtr hwnd, string text);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int GetClassName(IntPtr hwnd, StringBuilder buf, int max);

    [StructLayout(LayoutKind.Sequential)]
    struct RECT { public int Left, Top, Right, Bottom; }

    // The window the game is actually drawn in, found by class.
    //
    // It used to be found by size -- "the projector opens exactly one
    // top-level window of its own; the largest unowned one is it" -- and that
    // was wrong. Measured on this machine, the projector opens TWO unowned
    // top-level windows six milliseconds apart:
    //
    //      141 ms   966x709    class ShockwaveFlash   "Adobe Flash Player 32"
    //      147 ms   1920x1023  class Messaging        "Msg"
    //
    // The wrong one is nearly three times the bigger. Both carry a caption, a
    // system menu and a thick frame, so the styles do not separate them; only
    // the class does. Whenever the poll below landed after that six-millisecond
    // gap -- which is most of the time -- the helper was what got parked,
    // renamed and revealed, while the real window, started hidden, stayed
    // hidden. That is the "two windows and one of them is empty" that kept
    // coming back, and the reason the game sometimes could not be seen at all.
    //
    // MainWindowHandle is no use here for the original reason: it only returns
    // a window that is already visible, and this one is started hidden on
    // purpose.
    const string FLASH_CLASS = "ShockwaveFlash";

    public static IntPtr Find(Process game, int millis)
    {
        int deadline = Environment.TickCount + millis;
        StringBuilder cls = new StringBuilder(64);
        while (Environment.TickCount < deadline)
        {
            if (game.HasExited) return IntPtr.Zero;

            IntPtr best = IntPtr.Zero, fallback = IntPtr.Zero;
            long bestArea = 0, fallbackArea = 0;
            uint want = (uint)game.Id;
            EnumWindows(delegate(IntPtr h, IntPtr l)
            {
                uint pid;
                GetWindowThreadProcessId(h, out pid);
                if (pid != want) return true;
                if (GetWindow(h, GW_OWNER) != IntPtr.Zero) return true;
                RECT r;
                if (!GetWindowRect(h, out r)) return true;
                long area = (long)(r.Right - r.Left) * (r.Bottom - r.Top);
                if (area <= 0) return true;

                cls.Length = 0;
                bool flash = GetClassName(h, cls, cls.Capacity) > 0
                             && cls.ToString() == FLASH_CLASS;
                if (flash)
                {
                    if (area > bestArea) { bestArea = area; best = h; }
                }
                // Kept for a projector build whose window class is not this
                // one: better the old guess than no window at all. It is only
                // used when nothing of the right class was seen.
                else if (area > fallbackArea) { fallbackArea = area; fallback = h; }
                return true;
            }, IntPtr.Zero);

            if (best != IntPtr.Zero) return best;
            if (fallback != IntPtr.Zero && Environment.TickCount + 250 > deadline)
                return fallback;          // out of time; take what there is
            Thread.Sleep(2);      // tight: every millisecond here is a blink
        }
        return IntPtr.Zero;
    }

    public static void Park(IntPtr h)
    {
        if (h == IntPtr.Zero) return;
        try
        {
            SetWindowPos(h, IntPtr.Zero, PARKED, PARKED, 0, 0,
                         SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE);
            // Visible, and off screen. Hidden would be simpler and would cost
            // frames: Flash winds itself down when it thinks nobody is looking.
            ShowWindow(h, SW_SHOWNOACTIVATE);
        }
        catch { }
    }

    // The game is drawn 950 by 650 and the wrapper scales it while keeping
    // that shape (showAll). So the window is cut to the same shape: the
    // largest 950:650 rectangle the desktop has room for. Any other shape
    // would be the picture plus black bands, and stretching it to fill them
    // is what makes every face in the game squat.
    // The shape of the picture. It is the WRAPPER's stage, not the game's own
    // 950x650: under showAll the game reads Stage.width from whatever sits on
    // level 0, and lays itself out to that. Learned from the wrapper's header
    // rather than written down twice.
    static int ART_W = 950, ART_H = 650;

    public static void SetArt(int w, int h)
    {
        if (w > 0 && h > 0) { ART_W = w; ART_H = h; }
    }

    // How many times the picture's own size the window should be. Zero means
    // as large as the desktop allows. A smaller number is a sharper picture:
    // there are only 950x650 real pixels, and every one of them is spread
    // over Zoom*Zoom of the screen's.
    public static double Zoom;

    public static void Reveal(IntPtr h)
    {
        if (h == IntPtr.Zero) return;
        try
        {
            RECT r, c;
            if (GetWindowRect(h, out r) && GetClientRect(h, out c))
            {
                // The frame and menu bar are not part of the picture, so
                // they are measured and added on top of it.
                int chromeW = (r.Right - r.Left) - (c.Right - c.Left);
                int chromeH = (r.Bottom - r.Top) - (c.Bottom - c.Top);
                Rectangle area = Screen.PrimaryScreen.WorkingArea;
                int room_w = area.Width - chromeW, room_h = area.Height - chromeH;
                int w, ht;
                if (Zoom > 0)
                {
                    w = (int)Math.Round(ART_W * Zoom);
                    ht = (int)Math.Round(ART_H * Zoom);
                }
                else
                {
                    w = room_h * ART_W / ART_H;
                    ht = room_h;
                }
                // Never larger than the desktop, whatever was asked for.
                if (w > room_w) { w = room_w; ht = room_w * ART_H / ART_W; }
                if (ht > room_h) { ht = room_h; w = room_h * ART_W / ART_H; }
                w += chromeW;
                ht += chromeH;
                SetWindowPos(h, IntPtr.Zero,
                             area.X + (area.Width - w) / 2,
                             area.Y + (area.Height - ht) / 2,
                             w, ht, SWP_NOZORDER);
            }
            ShowWindow(h, SW_SHOW);
            SetForegroundWindow(h);
        }
        catch { }
    }

    // To the front, from the tray: restored if it was minimised.
    public static void Raise(IntPtr h)
    {
        if (h == IntPtr.Zero) return;
        try
        {
            if (IsIconic(h)) ShowWindow(h, 9 /* SW_RESTORE */);
            SetForegroundWindow(h);
        }
        catch { }
    }

    // Closed the way its own close box closes it.
    public static void Close(IntPtr h)
    {
        if (h != IntPtr.Zero) PostMessage(h, 0x0010 /* WM_CLOSE */, IntPtr.Zero, IntPtr.Zero);
    }

    // The projector titles its window after itself and offers no way to say
    // otherwise, so the name is set from out here. More than once, because the
    // player writes the title again during start-up and a single early rename
    // is simply overwritten.
    // The launcher's flame instead of Adobe's red F, on the title bar, the
    // task bar and Alt+Tab: WM_SETICON, the same way any program sets its
    // own, so the projector's file is left as Adobe signed it. The icons are
    // kept for the life of the process, the game window holds their handles.
    static Icon bigIcon, smallIcon;

    static void Brand(IntPtr h)
    {
        if (bigIcon == null)
        {
            Icon app = global::Brand.AppIcon();
            if (app == null) return;
            bigIcon = new Icon(app, SystemInformation.IconSize);
            smallIcon = new Icon(app, SystemInformation.SmallIconSize);
        }
        PostMessage(h, 0x0080 /* WM_SETICON */, (IntPtr)1 /* ICON_BIG */, bigIcon.Handle);
        PostMessage(h, 0x0080, IntPtr.Zero /* ICON_SMALL */, smallIcon.Handle);
    }

    public static void Title(IntPtr h, string text, Process game)
    {
        if (h == IntPtr.Zero) return;
        try
        {
            for (int i = 0; i < 12; i++)
            {
                SetWindowText(h, text);
                Brand(h);
                Thread.Sleep(500);
                if (game.HasExited) return;
            }
        }
        catch { /* a window with the wrong name above it is still a working game */ }
    }
}

// A still of the whole screen, laid over all of it for the moment the game's
// window would otherwise show itself white. The player sees nothing change.
// It never takes the focus, never shows in the task bar or Alt+Tab, and is
// revealed only once it has painted, for the same reason as the dialogs.
class Cover : Form
{
    readonly Bitmap shot;

    Cover()
    {
        FormBorderStyle = FormBorderStyle.None;
        ShowInTaskbar = false;
        StartPosition = FormStartPosition.Manual;
        TopMost = true;
        Bounds = SystemInformation.VirtualScreen;
        BackColor = Color.Black;
        Opacity = 0;
        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer, true);
        shot = new Bitmap(Bounds.Width, Bounds.Height);
        using (Graphics g = Graphics.FromImage(shot))
            g.CopyFromScreen(Bounds.Location, Point.Empty, Bounds.Size);
    }

    protected override bool ShowWithoutActivation { get { return true; } }

    protected override CreateParams CreateParams
    {
        get
        {
            CreateParams p = base.CreateParams;
            p.ExStyle |= 0x80 | 0x08000000;     // WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
            return p;
        }
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        e.Graphics.DrawImageUnscaled(shot, 0, 0);
    }

    /// <summary>On the window's thread: the still, on screen.</summary>
    public static Cover Lay()
    {
        Cover c = new Cover();
        try
        {
            c.Show();
            global::Modal.PaintNow(c);
            // Kept layered: going to 1.0 drops the style and repaints.
            c.Opacity = 254 / 255.0;
        }
        catch { }
        return c;
    }

    /// <summary>On the window's thread, any number of times.</summary>
    public void Lift()
    {
        if (IsDisposed) return;
        Close();
        shot.Dispose();
    }
}