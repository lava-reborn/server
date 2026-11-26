// The AVM1 client cannot remove Flash's Settings/About context-menu items.
// Route right clicks over the launched projector to the game player menu.
// The hook owns a message loop, does no I/O, and ends with that game process.
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Windows.Forms;

sealed class FlashContextMenu
{
    const int WH_MOUSE_LL = 14, WM_RBUTTONDOWN = 0x204, WM_RBUTTONUP = 0x205;
    const uint GA_ROOT = 2;
    const int PlayerMenuKey = 135, WM_KEYDOWN = 0x100, WM_KEYUP = 0x101; // F24 bridge.
    readonly ClickPair clicks = new ClickPair();
    readonly Process game;
    readonly uint gameId;
    readonly HookProc callback;

    delegate IntPtr HookProc(int code, IntPtr message, IntPtr data);
    [StructLayout(LayoutKind.Sequential)]
    struct POINT { public int X, Y; }
    [StructLayout(LayoutKind.Sequential)]
    struct RECT { public int Left, Top, Right, Bottom; }

    [DllImport("user32.dll", SetLastError = true)]
    static extern IntPtr SetWindowsHookEx(int kind, HookProc callback, IntPtr module, uint thread);
    [DllImport("user32.dll")] static extern bool UnhookWindowsHookEx(IntPtr hook);
    [DllImport("user32.dll")] static extern IntPtr CallNextHookEx(IntPtr hook, int code, IntPtr message, IntPtr data);
    [DllImport("user32.dll")] static extern IntPtr WindowFromPoint(POINT point);
    [DllImport("user32.dll")] static extern IntPtr GetAncestor(IntPtr window, uint flags);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr window, out uint process);
    [DllImport("user32.dll")] static extern bool GetClientRect(IntPtr window, out RECT rect);
    [DllImport("user32.dll")] static extern bool ScreenToClient(IntPtr window, ref POINT point);
    [DllImport("user32.dll", CharSet = CharSet.Unicode)]
    static extern int GetClassName(IntPtr window, StringBuilder name, int size);
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr window);
    [DllImport("user32.dll")] static extern bool PostMessage(IntPtr window, int message, IntPtr key, IntPtr flags);
    [DllImport("kernel32.dll", CharSet = CharSet.Unicode)]
    static extern IntPtr GetModuleHandle(string name);

    FlashContextMenu(Process game)
    {
        this.game = game;
        gameId = (uint)game.Id;
        callback = Mouse;
    }

    public static Thread Watch(Process game)
    {
        FlashContextMenu filter = new FlashContextMenu(game);
        Thread worker = new Thread(filter.Run);
        worker.IsBackground = true;
        worker.Name = "Flash context menu";
        worker.SetApartmentState(ApartmentState.STA);
        worker.Start();
        return worker;
    }

    static bool RightButton(int message)
    {
        return message == WM_RBUTTONDOWN || message == WM_RBUTTONUP;
    }

    internal static bool Suppress(int code, int message, uint process, uint game,
                                  string rootClass, bool insideClient)
    {
        return code >= 0 && RightButton(message) && process == game &&
               rootClass == "ShockwaveFlash" && insideClient;
    }

    // Pair only clicks whose press and release belong to the same game surface.
    internal sealed class ClickPair
    {
        IntPtr pressed;
        internal bool Accept(int message, IntPtr surface)
        {
            if (message == WM_RBUTTONDOWN)
            {
                pressed = surface;
                return false;
            }
            bool open = message == WM_RBUTTONUP && surface != IntPtr.Zero && surface == pressed;
            pressed = IntPtr.Zero;
            return open;
        }
    }

    bool Alive()
    {
        try { return !game.HasExited; }
        catch (InvalidOperationException) { return false; }
        catch (System.ComponentModel.Win32Exception) { return false; }
    }

    void Run()
    {
        if (!Alive()) return;
        IntPtr hook = SetWindowsHookEx(WH_MOUSE_LL, callback, GetModuleHandle(null), 0);
        if (hook == IntPtr.Zero)
        {
            Trace.TraceWarning("Flash context-menu filter: Win32 error {0}", Marshal.GetLastWin32Error());
            return;
        }
        try
        {
            using (System.Windows.Forms.Timer timer = new System.Windows.Forms.Timer())
            {
                timer.Interval = 250;
                timer.Tick += delegate { if (!Alive()) Application.ExitThread(); };
                timer.Start();
                Application.Run();
            }
        }
        finally
        {
            UnhookWindowsHookEx(hook);
            GC.KeepAlive(callback);
        }
    }

    IntPtr Mouse(int code, IntPtr message, IntPtr data)
    {
        if (code >= 0 && RightButton(message.ToInt32()) && Alive())
        {
            // MSLLHOOKSTRUCT starts with POINT; no other mouse data is read.
            POINT point = (POINT)Marshal.PtrToStructure(data, typeof(POINT));
            IntPtr hit = WindowFromPoint(point), surface = IntPtr.Zero;
            uint process;
            GetWindowThreadProcessId(hit, out process);
            if (process == gameId)
            {
                IntPtr window = GetAncestor(hit, GA_ROOT);
                StringBuilder name = new StringBuilder(64);
                GetClassName(window, name, name.Capacity);
                RECT rect;
                if (GetClientRect(window, out rect) && ScreenToClient(window, ref point))
                {
                    bool inside = point.X >= rect.Left && point.X < rect.Right &&
                                  point.Y >= rect.Top && point.Y < rect.Bottom;
                    if (Suppress(code, message.ToInt32(), process, gameId, name.ToString(), inside))
                        surface = hit;
                }
            }
            bool open = clicks.Accept(message.ToInt32(), surface);
            if (surface != IntPtr.Zero)
            {
                if (open)
                {
                    SetForegroundWindow(GetAncestor(surface, GA_ROOT));
                    // Only this movie receives F24. No synthetic left click, attack,
                    // movement, or global modifier-key state is generated.
                    if (PostMessage(surface, WM_KEYDOWN, new IntPtr(PlayerMenuKey), new IntPtr(1)))
                        PostMessage(surface, WM_KEYUP, new IntPtr(PlayerMenuKey), new IntPtr(unchecked((int)0xC0000001)));
                }
                return new IntPtr(1);
            }
        }
        return CallNextHookEx(IntPtr.Zero, code, message, data);
    }
}
