"""Compile and exercise local launcher parsing/guards; never shows a window."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class Launcher(unittest.TestCase):
    def test_status_validation_and_launch_guards(self):
        compiler = (Path(os.environ.get('WINDIR', r'C:\Windows'))
                    / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe')
        if os.name != 'nt' or not compiler.is_file():
            self.skipTest('Requires Windows .NET Framework compiler')
        source = r'''
using System;
using System.IO;
using System.Reflection;
using System.Windows.Forms;
class TesterLauncherChecks
{
    static void Check(bool value) { if (!value) throw new Exception("Launcher check failed"); }
    [STAThread] static void Main()
    {
        var valid = TesterLauncher.DecodeStatus("progress=100&ready=1&stage=Ready+now");
        Check(!TesterLauncher.Owns(valid, "mine"));
        Check(!TesterLauncher.Owns(TesterLauncher.DecodeStatus("progress=100&ready=1&stage=Ready&instance=other"), "mine"));
        Check(TesterLauncher.Owns(TesterLauncher.DecodeStatus("progress=100&ready=1&stage=Ready&instance=mine"), "mine"));
        Check(valid.Ready == 1 && valid.Progress == 100 && valid.Stage == "Ready now");
        Check(TesterLauncher.DecodeStatus("progress=1&ready=-1&stage=Error").Ready == -1);
        foreach (string invalid in new[] {
            "ready=1&progress=101&stage=bad", "ready=2&progress=5&stage=bad",
            "ready=1&progress=10", "progress=1&ready=no&stage=bad"
        })
        {
            bool refused = false;
            try { TesterLauncher.DecodeStatus(invalid); }
            catch (FormatException) { refused = true; }
            Check(refused);
        }
        var type = typeof(TesterLauncher);
        var flags = BindingFlags.NonPublic | BindingFlags.Static;
        type.GetField("root", flags).SetValue(null, Path.Combine(Path.GetTempPath(), Guid.NewGuid().ToString()));
        Label label = new Label();
        type.GetField("status", flags).SetValue(null, label);
        type.GetMethod("Play", flags).Invoke(null, null); // not ready: must not try to start
        Check(type.GetField("game", flags).GetValue(null) == null);
        type.GetField("ready", flags).SetValue(null, true);
        type.GetMethod("Play", flags).Invoke(null, null); // missing Flash: handled, no crash
        Check(label.Text.Length > 0);
        label.Dispose();
        Console.WriteLine("Launcher parser and guards OK");
    }
}
'''
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            checks = folder / 'Checks.cs'
            checks.write_text(source, encoding='utf-8')
            target = folder / 'Checks.exe'
            subprocess.run([
                str(compiler), '/nologo', '/main:TesterLauncherChecks',
                '/out:' + str(target), str(ROOT / 'tools/TesterLauncher.cs'),
                str(ROOT / 'launcher/Theme.cs'), str(checks),
            ], check=True, capture_output=True)
            result = subprocess.run([str(target)], check=True, capture_output=True,
                                    creationflags=subprocess.CREATE_NO_WINDOW, timeout=15)
            self.assertIn(b'Launcher parser and guards OK', result.stdout)


if __name__ == '__main__':
    unittest.main()
