"""Right-click isolation and the projector filter's lifetime; no game or visible windows."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ContextMenu(unittest.TestCase):
    def test_production_and_tester_builds_include_the_same_filter(self):
        for name in ('launcher/build.ps1', 'launcher/build.sh', 'tools/build_tester_launcher.py'):
            with self.subTest(build=name):
                self.assertIn('FlashContextMenu.cs', (ROOT / name).read_text(encoding='utf-8-sig'))
        self.assertEqual((ROOT / 'launcher/Launcher.cs').read_text(encoding='utf-8-sig').count(
            'FlashContextMenu.Watch(game);'), 2)  # automatic and manual login
        self.assertIn('FlashContextMenu.Watch(game);',
                      (ROOT / 'tools/TesterLauncher.cs').read_text(encoding='utf-8-sig'))

    def test_right_click_scope_and_real_hook_cleanup(self):
        compiler = (Path(os.environ.get('WINDIR', r'C:\Windows'))
                    / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe')
        if os.name != 'nt' or not compiler.is_file():
            self.skipTest('Native filter requires Windows .NET Framework')
        source = r'''using System;
using System.Diagnostics;
using System.Reflection;
using System.Threading;
class ContextMenuChecks
{
    static void Check(bool value) { if (!value) throw new Exception("Context menu check failed"); }
    [STAThread] static void Main(string[] args)
    {
        if (args.Length != 0) { Thread.Sleep(2000); return; }
        uint game = 42;
        foreach (int message in new[] {0x204, 0x205})
        {
            Check(FlashContextMenu.Suppress(0, message, game, game, "ShockwaveFlash", true));
            Check(!FlashContextMenu.Suppress(-1, message, game, game, "ShockwaveFlash", true));
            Check(!FlashContextMenu.Suppress(0, message, game + 1, game, "ShockwaveFlash", true));
            Check(!FlashContextMenu.Suppress(0, message, game, game, "ShockwaveFlash", false));
            foreach (string root in new[] {"#32768", "Messaging", "WindowsForms10", "", null})
                Check(!FlashContextMenu.Suppress(0, message, game, game, root, true));
        }
        foreach (int message in new[] {0x200, 0x201, 0x202, 0x203, 0x207, 0x208, 0x20A, 0x20B})
            Check(!FlashContextMenu.Suppress(0, message, game, game, "ShockwaveFlash", true));
        FlashContextMenu.ClickPair clicks = new FlashContextMenu.ClickPair();
        IntPtr first = new IntPtr(1), second = new IntPtr(2);
        Check(!clicks.Accept(0x205, first)); // Release without press.
        Check(!clicks.Accept(0x204, first));
        Check(clicks.Accept(0x205, first));
        Check(!clicks.Accept(0x205, first)); // No duplicate opening.
        Check(!clicks.Accept(0x204, first));
        Check(!clicks.Accept(0x205, second)); // Another surface.
        Check(!clicks.Accept(0x204, first));
        Check(!clicks.Accept(0x205, IntPtr.Zero)); // Release outside game.
        Check(!clicks.Accept(0x205, first));
        Check(!clicks.Accept(0x204, IntPtr.Zero));
        Check(!clicks.Accept(0x205, first)); // Press outside game.
        // A windowless child owns no pointer target: installing this hook
        // cannot suppress any input to the user's applications.
        ProcessStartInfo start = new ProcessStartInfo(Assembly.GetExecutingAssembly().Location, "child");
        start.UseShellExecute = false;
        start.CreateNoWindow = true;
        start.WindowStyle = ProcessWindowStyle.Hidden;
        using (Process child = Process.Start(start))
        {
            Thread filter = FlashContextMenu.Watch(child);
            Check(filter.IsBackground);
            Check(!filter.Join(250)); // SetWindowsHookEx succeeded and its loop stays alive.
            Check(child.WaitForExit(5000));
            Check(filter.Join(3000)); // The native hook and message loop end with the process.
        }
        Console.WriteLine("Context menu scope and lifecycle OK");
    }
}
'''
        with tempfile.TemporaryDirectory(prefix='flash_context_menu_') as folder:
            folder = Path(folder)
            checks = folder / 'Checks.cs'
            checks.write_text(source, encoding='utf-8')
            target = folder / 'Checks.exe'
            subprocess.run([str(compiler), '/nologo', '/target:exe', '/out:' + str(target),
                            str(ROOT / 'launcher/FlashContextMenu.cs'), str(checks)],
                           check=True, capture_output=True)
            result = subprocess.run([str(target)], check=True, capture_output=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            self.assertIn(b'Context menu scope and lifecycle OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
