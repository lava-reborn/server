"""Compile only the local tester launcher; never copies or archives game assets."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def build(out):
    out = Path(out).resolve()
    compiler = (Path(os.environ.get('WINDIR', r'C:\Windows'))
                / 'Microsoft.NET/Framework64/v4.0.30319/csc.exe')
    if not compiler.is_file():
        raise RuntimeError('Windows .NET Framework C# compiler not found')
    subprocess.run([
        str(compiler), '/nologo', '/target:winexe',
        '/out:' + str(out / 'TestLauncher.exe'),
        '/win32icon:' + str(ROOT / 'launcher/assets/lava.ico'),
        '/resource:' + str(ROOT / 'launcher/assets/hero.jpg') + ',hero',
        '/resource:' + str(ROOT / 'launcher/assets/logo.png') + ',logo',
        str(ROOT / 'launcher/Theme.cs'),
        str(ROOT / 'tools/TesterLauncher.cs'),
    ], check=True)
    (out / 'Start.cmd').write_bytes(
        b'@echo off\r\ncd /d "%~dp0"\r\nstart "" "%~dp0TestLauncher.exe"\r\n')
    (out / 'Start.vbs').write_text(
        'Option Explicit\nDim shell, root\n'
        'Set shell = CreateObject("WScript.Shell")\n'
        'root = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)\n'
        'shell.CurrentDirectory = root\n'
        'shell.Run Chr(34) & root & "\\TestLauncher.exe" & Chr(34), 1, False\n',
        encoding='ascii')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('out', type=Path)
    build(parser.parse_args().out)
