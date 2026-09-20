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
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr hwnd, int cmd);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr hwnd, IntPtr after,
                                                             int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr hwnd);
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool SetWindowText(IntPtr hwnd, string text);

    [StructLayout(LayoutKind.Sequential)]
    struct RECT { public int Left, Top, Right, Bottom; }

    // MainWindowHandle only ever finds a window that is already visible, and
    // this one is started hidden on purpose, so the process is enumerated by
    // hand. The projector opens exactly one top-level window of its own; the
    // largest unowned one is it.
    public static IntPtr Find(Process game, int millis)
    {
        int deadline = Environment.TickCount + millis;
        while (Environment.TickCount < deadline)
        {
            if (game.HasExited) return IntPtr.Zero;

            IntPtr best = IntPtr.Zero;
            long bestArea = 0;
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
                if (area > bestArea) { bestArea = area; best = h; }
                return true;
            }, IntPtr.Zero);

            if (best != IntPtr.Zero && bestArea > 0) return best;
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

    public static void Reveal(IntPtr h)
    {
        if (h == IntPtr.Zero) return;
        try
        {
            RECT r;
            if (GetWindowRect(h, out r))
            {
                int w = r.Right - r.Left, ht = r.Bottom - r.Top;
                Rectangle area = Screen.PrimaryScreen.WorkingArea;
                SetWindowPos(h, IntPtr.Zero,
                             area.X + (area.Width - w) / 2,
                             area.Y + (area.Height - ht) / 2,
                             0, 0, SWP_NOSIZE | SWP_NOZORDER);
            }
            ShowWindow(h, SW_SHOW);
            SetForegroundWindow(h);
        }
        catch { }
    }

    // The projector titles its window after itself and offers no way to say
    // otherwise, so the name is set from out here. More than once, because the
    // player writes the title again during start-up and a single early rename
    // is simply overwritten.
    public static void Title(IntPtr h, string text, Process game)
    {
        if (h == IntPtr.Zero) return;
        try
        {
            for (int i = 0; i < 12; i++)
            {
                SetWindowText(h, text);
                Thread.Sleep(500);
                if (game.HasExited) return;
            }
        }
        catch { /* a window with the wrong name above it is still a working game */ }
    }
}
