// The names over the global map's cells, with the owner's edits laid on.
//
// res/database/locations.xml is the player's own file: 414 rows of
// <location x="" y="" text="" /> that the client draws over the map itself;
// nothing the server sends touches them. The owner can hide a row or give it
// another text (data/map_labels.json). The build embeds those edits as
// map_labels.txt (tools/export_map_labels.py), and LocalServer serves the
// player's file through Apply. server/map_labels.py does the same for a
// local run; the two are held to the same result.
//
// A row is edited only when its cell AND its current text match an edit, so
// another copy of the client is never changed by mistake; every other byte is
// served as it is on disk; and any failure serves the file untouched -- a map
// with an old name beats a map with none.
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Reflection;
using System.Security;
using System.Text;
using System.Text.RegularExpressions;

static class MapLabels
{
    internal sealed class Edit
    {
        public bool Hide;
        public string Text;
    }

    // One row with the line break after it, so a hidden row leaves no gap.
    static readonly Regex Row = new Regex(@"<location\b[^>]*?/>[ \t]*(\r?\n)?");
    static readonly Regex Attr = new Regex(@"\b(x|y|text)\s*=\s*""([^""]*)""");

    static Dictionary<string, Edit> embedded;

    /// <summary>The player's locations.xml with the embedded edits made.</summary>
    public static byte[] Apply(byte[] raw)
    {
        if (embedded == null)
        {
            Dictionary<string, Edit> r = new Dictionary<string, Edit>(StringComparer.Ordinal);
            try
            {
                using (Stream s = Assembly.GetExecutingAssembly().GetManifestResourceStream("map_labels.txt"))
                    if (s != null)
                        using (StreamReader rd = new StreamReader(s, new UTF8Encoding(false)))
                            r = Parse(rd.ReadToEnd());
            }
            catch { }
            embedded = r;
        }
        return Apply(raw, embedded);
    }

    /// <summary>tools/export_map_labels.py's lines: x, y, was, hide|text, new text.</summary>
    internal static Dictionary<string, Edit> Parse(string rules)
    {
        Dictionary<string, Edit> r = new Dictionary<string, Edit>(StringComparer.Ordinal);
        foreach (string line in rules.Replace("\r", "").Split('\n'))
        {
            if (line.Length == 0 || line[0] == '#') continue;
            string[] f = line.Split('\t');
            if (f.Length < 4) continue;
            Edit e = new Edit();
            e.Hide = f[3] == "hide";
            e.Text = f.Length > 4 ? f[4] : "";
            r[f[0] + "," + f[1] + "\t" + f[2]] = e;
        }
        return r;
    }

    internal static byte[] Apply(byte[] raw, Dictionary<string, Edit> edits)
    {
        if (raw == null || edits == null || edits.Count == 0) return raw;
        try
        {
            bool bom = raw.Length >= 3 && raw[0] == 0xEF && raw[1] == 0xBB && raw[2] == 0xBF;
            int skip = bom ? 3 : 0;
            string doc = new UTF8Encoding(false, true).GetString(raw, skip, raw.Length - skip);
            int changed = 0;
            string edited = Row.Replace(doc, delegate(Match m)
            {
                string x = null, y = null, t = null;
                foreach (Match a in Attr.Matches(m.Value))
                {
                    string k = a.Groups[1].Value, v = a.Groups[2].Value;
                    if (k == "x") x = v; else if (k == "y") y = v; else t = v;
                }
                Edit e;
                if (x == null || y == null || t == null
                    || !edits.TryGetValue(x + "," + y + "\t" + WebUtility.HtmlDecode(t), out e))
                    return m.Value;
                changed++;
                if (e.Hide) return "";
                string value = SecurityElement.Escape(e.Text);
                return Attr.Replace(m.Value, delegate(Match a)
                {
                    return a.Groups[1].Value == "text" ? "text=\"" + value + "\"" : a.Value;
                });
            });
            if (changed == 0) return raw;
            byte[] body = new UTF8Encoding(false).GetBytes(edited);
            if (!bom) return body;
            byte[] all = new byte[body.Length + 3];
            all[0] = 0xEF; all[1] = 0xBB; all[2] = 0xBF;
            Buffer.BlockCopy(body, 0, all, 3, body.Length);
            return all;
        }
        catch { return raw; }
    }
}
