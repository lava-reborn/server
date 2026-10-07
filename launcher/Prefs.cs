// What the launcher remembers about itself between starts: the game folder
// the player chose, and the version they last saw -- so "Что нового" shows
// once after an update and then goes away.
//
// A few key=value lines in %LOCALAPPDATA%\LavaOnline\settings, beside the
// remembered account and the resource cache. Nothing here is secret and
// nothing here is needed to play: a missing or unreadable file is the same
// as a fresh install.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;

static class Prefs
{
    static Dictionary<string, string> map;

    static string Path()
    {
        string dir = System.IO.Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "LavaOnline");
        Directory.CreateDirectory(dir);
        return System.IO.Path.Combine(dir, "settings");
    }

    static void Load()
    {
        if (map != null) return;
        map = new Dictionary<string, string>();
        try
        {
            if (!File.Exists(Path())) return;
            foreach (string line in File.ReadAllLines(Path(), Encoding.UTF8))
            {
                int eq = line.IndexOf('=');
                if (eq <= 0) continue;
                map[line.Substring(0, eq).Trim()] = line.Substring(eq + 1).Trim();
            }
        }
        catch { }
    }

    public static string Get(string key)
    {
        Load();
        string v;
        return map.TryGetValue(key, out v) ? v : null;
    }

    public static void Set(string key, string value)
    {
        Load();
        if (value == null) map.Remove(key);
        else map[key] = value;
        try
        {
            StringBuilder sb = new StringBuilder();
            foreach (KeyValuePair<string, string> kv in map)
                sb.Append(kv.Key).Append('=').Append(kv.Value).Append("\r\n");
            File.WriteAllText(Path(), sb.ToString(), new UTF8Encoding(false));
        }
        catch { /* not being able to remember is not a reason to not play */ }
    }

    // The folder that holds res\main.swf: the one the player chose, else the
    // one beside the exe.
    public const string GameDir = "game_dir";
    // The launcher version last shown, for the "what's new" mark.
    public const string SeenVersion = "seen_version";
    // Set by "Выйти" on a remembered account: the next start shows the login,
    // filled in, rather than the card. Cleared by the next sign-in.
    public const string SignedOut = "signed_out";
}
