// The credential, and the one place it is written down.
//
// The password never leaves this machine: the client hashes it and sends only
// the digest, the server stores only the digest, and so does "remember me".
// That is the game's own scheme (EnterGameInterface.startSession hashes
// pass + login and keeps the result in a SharedObject), reproduced here byte
// for byte -- server/accounts.py:231 is the other half of it.
using System;
using System.IO;
using System.Security.Cryptography;
using System.Text;

static class Creds
{
    // md5 of cp1251(password + login), lower-case hex. The cyrillic range is
    // the only reason the code page matters, and MD5rus.convertToCP1251 is
    // where the client does the same thing.
    public static string Hash(string password, string login)
    {
        byte[] bytes = Encoding.GetEncoding(1251).GetBytes(password + login);
        using (MD5 md5 = MD5.Create())
        {
            byte[] digest = md5.ComputeHash(bytes);
            StringBuilder sb = new StringBuilder(32);
            foreach (byte b in digest) sb.Append(b.ToString("x2"));
            return sb.ToString();
        }
    }

    static string Path()
    {
        string dir = System.IO.Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "LavaOnline");
        Directory.CreateDirectory(dir);
        return System.IO.Path.Combine(dir, "account");
    }

    // Remembering means keeping the digest, which is as good as the password:
    // it is the whole credential. So it goes through DPAPI under the current
    // user -- another account on the same machine cannot read it back, and it
    // is useless on any other machine.
    public static void Save(string login, string hash)
    {
        try
        {
            byte[] blob = ProtectedData.Protect(Encoding.UTF8.GetBytes(hash), null,
                                                DataProtectionScope.CurrentUser);
            File.WriteAllText(Path(), login + "\n" + Convert.ToBase64String(blob),
                              new UTF8Encoding(false));
        }
        catch { /* not being able to remember is not a reason to not play */ }
    }

    public static void Forget()
    {
        try { File.Delete(Path()); }
        catch { }
    }

    // Returns the saved login, or null. The digest comes back through hash.
    public static string Load(out string hash)
    {
        hash = null;
        try
        {
            string p = Path();
            if (!File.Exists(p)) return null;
            string[] lines = File.ReadAllText(p, Encoding.UTF8).Split('\n');
            if (lines.Length < 2) return null;
            byte[] blob = Convert.FromBase64String(lines[1].Trim());
            hash = Encoding.UTF8.GetString(
                ProtectedData.Unprotect(blob, null, DataProtectionScope.CurrentUser));
            return lines[0].Trim();
        }
        catch
        {
            // A file from another user or another machine will not unprotect.
            // That is a forgotten password, not an error worth a window.
            return null;
        }
    }
}
