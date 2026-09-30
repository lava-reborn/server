// Keeping what the server generates and what the player holds in step.
//
// One file matters, and it matters more than its size suggests:
// res/database/texts.xml. Every name, quest line and item label reaches the
// client as a numeric string id and is resolved through this table in one
// batch before login. An id the table does not hold is not a blank label:
// StringCollector fetches the missing batch, SBase answers its own "update"
// event by reloading and dispatching onLoad, and Session handles that with
// SceneShifter.enterScene() -- which is the login screen. A table that has
// fallen behind the server is therefore a session that ends by itself, and
// that is why the launcher would rather bar the way in than let somebody play
// with one.
//
// The player's own res/ is not touched and never travels: only the documents
// this project generates are fetched, into a cache of our own.
//
// THREE THINGS HERE WERE MEASURED RATHER THAN ASSUMED.
//
// 1. TLS has to be raised by hand. build.ps1 emits no TargetFrameworkAttribute
//    and writes no .config beside the exe, so the runtime treats the assembly
//    as targeting 4.0 and starts life with SecurityProtocol = Ssl3 | Tls. A
//    probe compiled with exactly that command answered every https:// request
//    with SecureChannelFailure, and the same WebClient in the same process
//    succeeded one line later once the protocol was raised. Without the
//    assignment below this whole file would be a silent no-op -- and a silent
//    no-op looks exactly like "you are up to date".
//
// 2. The digest is stable, so comparing digests does not mean downloading
//    1.9 MB on every start. names.document() joins sorted(ALL.items()) over
//    integer keys, the table is built once at import and never written to
//    again, and five processes across two interpreters and four
//    PYTHONHASHSEED values all produced the same digest.
//
// 3. It compresses well: 1 915 490 bytes raw against about 240 KB gzipped.
//    That is the difference between a wait and no wait, which is why
//    AutomaticDecompression is on -- and why nothing here checks
//    Content-Length, because a decompressed body has none.
using System;
using System.IO;
using System.Net;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using System.Threading;

enum UpState
{
    Checking,     // still asking
    Ready,        // the table on hand is the table the server will speak
    Downloading,  // fetching it
    MustUpdate,   // this exe is not the published one; the way in is barred
    Unchecked,    // the server could not be asked at all
}

static class Updater
{
    // Generous, because it is never on the way in: the check runs while the
    // player is still reading the window.
    const int TIMEOUT_MS = 8000;
    // A ceiling for anything read off the network. The table is 1.9 MB and
    // has grown by tens of kilobytes at a time; 32 MB is far past any honest
    // value and still far short of filling a disk.
    const int MAX_BYTES = 32 * 1024 * 1024;

    static readonly object gate = new object();
    static UpState state = UpState.Checking;
    static string note = "Проверяем обновления";
    static string downloadUrl;
    static byte[] fresh;                 // what the server has, once verified
    static Func<byte[]> embedded;        // the copy compiled into this exe
    static byte[] embeddedBlob;
    static readonly ManualResetEvent settled = new ManualResetEvent(false);

    public static UpState State { get { lock (gate) return state; } }
    public static string Note { get { lock (gate) return note; } }
    public static string DownloadUrl { get { lock (gate) return downloadUrl; } }

    // Raised on the UI thread by Launcher whenever the state moves.
    public static Action Changed;

    static void Move(UpState s, string text)
    {
        lock (gate) { state = s; note = text; }
        Action a = Changed;
        if (a != null) a();
    }

    /// <summary>Begin the check. Returns at once; everything happens on its
    /// own thread, and nothing here ever throws into the caller.</summary>
    public static void Start(string site, Func<byte[]> embeddedTexts)
    {
        embedded = embeddedTexts;
        Thread t = new Thread(delegate ()
        {
            try { Run(site); }
            catch (Exception e)
            {
                // Fail open, but never fail quiet: "could not ask" and "nothing
                // to do" must not look the same, because that is precisely how
                // a dead channel hides. The TLS fault above would have looked
                // like this for ever.
                Move(UpState.Unchecked, "Обновления проверить не удалось: " + Short(e));
            }
            settled.Set();
        });
        t.IsBackground = true;
        t.Start();
    }

    /// <summary>Wait for the check to finish, up to a point. Called on the way
    /// in, where the player is already looking at "Запускаем игру".</summary>
    public static bool Wait(int millis)
    {
        try { return settled.WaitOne(millis); }
        catch { return true; }
    }

    /// <summary>The bytes LocalServer should serve as res/database/texts.xml:
    /// what the server has if we got it, the compiled-in copy otherwise. No
    /// file is read here -- this is on the way in, and the cache was loaded on
    /// the background thread long before.</summary>
    public static byte[] Texts()
    {
        byte[] b;
        lock (gate) b = fresh;
        return b != null ? b : Embedded();
    }

    static byte[] Embedded()
    {
        lock (gate)
        {
            if (embeddedBlob == null && embedded != null) embeddedBlob = embedded();
            return embeddedBlob;
        }
    }

    // --- the run ------------------------------------------------------------

    static void Run(string site)
    {
        Tls();

        if (Flag("LAVA_NOUPDATE"))
        {
            Move(UpState.Unchecked, "Проверка обновлений выключена");
            return;
        }
        if (string.IsNullOrEmpty(site))
        {
            Move(UpState.Unchecked, "Адрес обновлений не задан");
            return;
        }
        site = site.TrimEnd('/');

        // The launcher first. If this exe is not the published one there is no
        // point spending the player's bandwidth on a table that the new exe
        // brings with it anyway.
        string url;
        if (Stale(site, out url))
        {
            lock (gate) downloadUrl = url;
            Move(UpState.MustUpdate, "Вышла новая версия лаунчера — обновитесь, чтобы играть");
            return;
        }

        string want, from;
        long size;
        int rows;
        if (!Manifest(site, out want, out size, out rows, out from))
        {
            Move(UpState.Unchecked, "Сервер обновлений не ответил — играем на своей копии");
            return;
        }

        // Already holding it? Two cheap answers before any download.
        if (Same(Sha(Embedded()), want))
        {
            Move(UpState.Ready, "Ресурсы актуальны");
            return;
        }
        byte[] cached = Cache.Load(want, Sha(Embedded()));
        if (cached != null)
        {
            lock (gate) fresh = cached;
            Move(UpState.Ready, "Ресурсы актуальны");
            return;
        }

        Move(UpState.Downloading, "Загружаем обновление ресурсов");
        byte[] blob = Fetch(site + from, size);
        if (blob == null)
        {
            // Fetch swallows everything -- timeout, broken TLS, a 502 from the
            // front, a body longer than promised -- so without this the player
            // is told the checksum did not match, which sends whoever reads the
            // report looking in the wrong place entirely.
            Move(UpState.Unchecked,
                 "Не удалось скачать обновление — играем на своей копии");
            return;
        }
        string got = Sha(blob);
        if (!Same(got, want))
        {
            Move(UpState.Unchecked,
                 "Обновление не сошлось по контрольной сумме — играем на своей копии");
            return;
        }
        if (!Sane(blob, rows))
        {
            Move(UpState.Unchecked,
                 "Обновление не прошло проверку — играем на своей копии");
            return;
        }
        lock (gate) fresh = blob;
        Cache.Save(blob, want, Sha(Embedded()));
        Move(UpState.Ready, "Ресурсы обновлены");
    }

    // The .NET Framework quirk this file exists around. Assignment rather than
    // an |=, so Ssl3 is dropped rather than kept; named constants, because the
    // compiler build.ps1 uses resolves System.dll out of a v4.0.30319 that has
    // been serviced up to 4.8 and knows them. Never fatal: a machine whose
    // registry already forces a modern default still works if this throws.
    static void Tls()
    {
        try
        {
            ServicePointManager.SecurityProtocol =
                SecurityProtocolType.Tls12 | SecurityProtocolType.Tls11 |
                SecurityProtocolType.Tls;
        }
        catch { }
    }

    // --- asking -------------------------------------------------------------

    // The manifest is a document this project writes and this project reads,
    // and the answer is four fields. Pulling them out with expressions rather
    // than adding a serializer reference is the smaller of the two liberties:
    // no new assembly to ship, and a malformed answer simply fails to match
    // and is treated as no answer at all.
    static readonly Regex RX_SHA = new Regex("\"sha256\"\\s*:\\s*\"([0-9a-fA-F]{64})\"");
    static readonly Regex RX_SIZE = new Regex("\"size\"\\s*:\\s*([0-9]{1,12})");
    static readonly Regex RX_ROWS = new Regex("\"rows\"\\s*:\\s*([0-9]{1,12})");
    static readonly Regex RX_URL = new Regex("\"url\"\\s*:\\s*\"([^\"]{1,200})\"");

    static bool Manifest(string site, out string sha, out long size, out int rows, out string url)
    {
        sha = null; size = 0; rows = 0; url = null;
        string body = Text(site + "/exe/lavaclient/manifest");
        if (body == null) return false;

        Match m = RX_SHA.Match(body);
        if (!m.Success) return false;
        sha = m.Groups[1].Value.ToLowerInvariant();

        m = RX_SIZE.Match(body);
        if (m.Success) long.TryParse(m.Groups[1].Value, out size);
        m = RX_ROWS.Match(body);
        if (m.Success) int.TryParse(m.Groups[1].Value, out rows);

        m = RX_URL.Match(body);
        url = m.Success ? m.Groups[1].Value : "/exe/lavaclient/texts.xml";
        // Only our own server, and only a path: a manifest that has been
        // tampered with cannot send the launcher somewhere else.
        if (!url.StartsWith("/")) return false;
        return size > 0 && size <= MAX_BYTES;
    }

    // Is this exe the one the site is handing out? The site already publishes
    // the digest of the published file, so there is no version number to keep
    // in step by hand and nothing to get wrong at deploy time: the question is
    // simply whether this file is that file.
    //
    // A build pointed at anything but the real site -- a local server, a test
    // host -- gets a 404 here and is left alone, which is what lets the
    // machine this was written on run its own builds.
    static bool Stale(string site, out string url)
    {
        url = site + "/";
        string body = Text(site + "/api/client");
        if (body == null) return false;

        Match m = RX_SHA.Match(body);
        if (!m.Success) return false;
        string published = m.Groups[1].Value.ToLowerInvariant();

        m = RX_URL.Match(body);
        if (m.Success && m.Groups[1].Value.StartsWith("/")) url = site + m.Groups[1].Value;

        string mine = Self();
        if (mine == null) return false;        // cannot tell, so do not bar
        return !Same(mine, published);
    }

    static string Self()
    {
        try
        {
            string path = Assembly.GetExecutingAssembly().Location;
            if (string.IsNullOrEmpty(path) || !File.Exists(path)) return null;
            using (FileStream fs = File.OpenRead(path))
            using (SHA256 h = SHA256.Create())
                return Hex(h.ComputeHash(fs));
        }
        catch { return null; }
    }

    static string Text(string url)
    {
        byte[] b = Fetch(url, 1024 * 1024);
        if (b == null) return null;
        try { return Encoding.UTF8.GetString(b); }
        catch { return null; }
    }

    static byte[] Fetch(string url, long expected)
    {
        try
        {
            HttpWebRequest rq = (HttpWebRequest)WebRequest.Create(url);
            rq.Timeout = TIMEOUT_MS;
            rq.ReadWriteTimeout = TIMEOUT_MS;
            rq.UserAgent = "LavaReborn";
            // Without this the table arrives as 1 915 490 bytes instead of
            // about 240 KB. With it there is no Content-Length to check, so
            // the size ceiling below is counted off the stream instead.
            rq.AutomaticDecompression = DecompressionMethods.GZip | DecompressionMethods.Deflate;
            using (WebResponse rs = rq.GetResponse())
            using (Stream s = rs.GetResponseStream())
            using (MemoryStream m = new MemoryStream())
            {
                byte[] buf = new byte[64 * 1024];
                long cap = expected > 0 && expected < MAX_BYTES ? expected + 4096 : MAX_BYTES;
                int n;
                while ((n = s.Read(buf, 0, buf.Length)) > 0)
                {
                    if (m.Length + n > cap) return null;   // longer than promised
                    m.Write(buf, 0, n);
                }
                return m.ToArray();
            }
        }
        catch { return null; }
    }

    // --- checking what arrived ----------------------------------------------

    // The digest already proves the bytes are the ones the server sent. This
    // asks the other question -- whether the server should be sending them at
    // all -- and it is worth asking because these strings do not end up in a
    // label. They reach TextField.htmlText (QuestInterface, Hint, Annotation),
    // the client unescapes them on the way, and AVM1 html understands
    // <a href="asfunction:..."> and <img src="...swf"> inside an unpatched
    // Flash 32 that this launcher starts itself. So a compromised server would
    // otherwise have a path straight into the player's projector.
    //
    // The whitelist is not guesswork: the live table holds 359 <br>, one
    // <hint> and one </hint>, and nothing else. Anything richer than that is
    // not a name.
    // Only these may appear as a tag once a value has been unescaped, and the
    // list is not a guess: it is exactly the markup the game's own original
    // string table uses, measured over all 62 795 of its rows -- line breaks,
    // bold, italic, underline and the green <hint>, with the self-closing
    // <br/> and <B/> that the writers of 2008 also typed. There is not one link,
    // one image, one attribute or one asfunction in the whole file, which is
    // why admitting formatting costs the defence nothing: a tag that could run
    // code or fetch a film is still refused, whatever else a value carries.
    static readonly string[] ALLOWED_TAGS = {
        "br", "/br", "br/",
        "b", "/b", "b/",
        "i", "/i",
        "u", "/u",
        "hint", "/hint",
    };

    static bool Sane(byte[] blob, int rows)
    {
        if (blob == null || blob.Length < 32) return false;
        if (blob[0] != 0xEF || blob[1] != 0xBB || blob[2] != 0xBF) return false;

        string s;
        try { s = Encoding.UTF8.GetString(blob); }
        catch { return false; }

        const string HEAD = "﻿<?xml version='1.0'?><data>";
        if (!s.StartsWith(HEAD, StringComparison.Ordinal)) return false;
        // A download cut in half still parses as a prefix, so the end is
        // checked rather than assumed.
        if (!s.EndsWith("</data>", StringComparison.Ordinal)) return false;

        int at = HEAD.Length;
        int tail = s.Length - "</data>".Length;
        int seen = 0;
        while (at < tail)
        {
            if (string.CompareOrdinal(s, at, "<s id='", 0, 7) != 0) return false;
            int q = s.IndexOf("'>", at + 7, StringComparison.Ordinal);
            if (q < 0) return false;
            for (int i = at + 7; i < q; i++)
                if (s[i] < '0' || s[i] > '9') return false;      // ids are numbers
            int close = s.IndexOf("</s>", q + 2, StringComparison.Ordinal);
            if (close < 0) return false;
            if (!SafeValue(s.Substring(q + 2, close - q - 2))) return false;
            at = close + 4;
            seen++;
        }
        if (at != tail) return false;
        if (rows > 0 && seen < rows) return false;
        if (seen < 1000) return false;      // a table this small is not this game
        return true;
    }

    // Why a whitelist and not a list of things to refuse.
    //
    // These strings do not end up in a label. They reach TextField.htmlText
    // (QuestInterface, Hint, Annotation), the client unescapes them on the way,
    // and AVM1 html understands <a href="asfunction:..."> -- a call into the
    // movie on click -- and <img src="...swf">, which loads an outside film
    // into the field, inside an unpatched Flash 32 that this launcher starts
    // itself. So a compromised server would otherwise have a road straight
    // into the player's projector, and the digest does not close it: the
    // digest only proves the bytes are the ones the server sent.
    //
    // A list of forbidden spellings was tried first and it leaked badly. A tab
    // instead of a space walked "<a	href=" straight past "<a "; so did a
    // newline, an upper-case IMG, "asfunction&#58;" with the colon as a
    // numeric entity, "&#60;img" with the bracket as one, a value escaped
    // twice over, and <embed>, <object> and <iframe>, which were only ever
    // refused in their escaped spelling. Every one of those is refused here
    // for the same reason and without naming it: the server escapes &, < and >
    // in every value, so a value holding a raw angle bracket is already wrong,
    // and after unescaping there is nothing to argue about -- the tag either
    // is one of the four or it is not.
    static bool SafeValue(string v)
    {
        // The server escapes every bracket, so a raw one never belongs here.
        if (v.IndexOf('<') >= 0 || v.IndexOf('>') >= 0) return false;
        if (v.IndexOf('&') < 0) return true;         // nothing escaped, nothing to decode

        // Decode until it stops changing -- twice over is what a value escaped
        // twice needs -- and check what comes out each time.
        for (int pass = 0; pass < 4; pass++)
        {
            string next;
            try { next = WebUtility.HtmlDecode(v); }
            catch { return false; }
            if (string.Equals(next, v, StringComparison.Ordinal)) return true;
            v = next;
            if (!TagsAllowed(v)) return false;
        }
        return true;
    }

    static bool TagsAllowed(string v)
    {
        int i = 0;
        while ((i = v.IndexOf('<', i)) >= 0)
        {
            int j = i + 1;
            while (j < v.Length && v[j] != '>' && v[j] != '<') j++;
            string tag = v.Substring(i + 1, j - i - 1).Trim().ToLowerInvariant();
            bool ok = false;
            for (int k = 0; k < ALLOWED_TAGS.Length; k++)
                if (string.Equals(tag, ALLOWED_TAGS[k], StringComparison.Ordinal)) { ok = true; break; }
            if (!ok) return false;
            i = j >= v.Length ? v.Length : j + 1;
        }
        return true;
    }

    // --- odds and ends ------------------------------------------------------

    static string Sha(byte[] b)
    {
        if (b == null) return null;
        using (SHA256 h = SHA256.Create()) return Hex(h.ComputeHash(b));
    }

    static string Hex(byte[] d)
    {
        StringBuilder sb = new StringBuilder(d.Length * 2);
        foreach (byte b in d) sb.Append(b.ToString("x2"));
        return sb.ToString();
    }

    static bool Same(string a, string b)
    {
        return a != null && b != null && string.Equals(a, b, StringComparison.OrdinalIgnoreCase);
    }

    static bool Flag(string name)
    {
        string v = Environment.GetEnvironmentVariable(name);
        if (v == null) return false;
        v = v.Trim().ToLowerInvariant();
        return v != "" && v != "0" && v != "no" && v != "off" && v != "false";
    }

    static string Short(Exception e)
    {
        string m = e.Message;
        if (m == null) return e.GetType().Name;
        m = m.Replace("\r", " ").Replace("\n", " ").Trim();
        return m.Length > 120 ? m.Substring(0, 120) + "…" : m;
    }
}

// The cache. Beside the remembered account rather than beside the exe: the
// folder the game is unpacked into may be read-only, may be inside OneDrive,
// and is in any case the player's, not ours.
static class Cache
{
    static string Dir()
    {
        string d = Path.Combine(
            Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),
            "LavaOnline", "cache");
        Directory.CreateDirectory(d);
        return d;
    }

    static string Blob() { return Path.Combine(Dir(), "texts.xml"); }
    static string Mark() { return Path.Combine(Dir(), "texts.mark"); }

    /// <summary>The cached table, if it is both what the server wants and
    /// newer than the copy inside this exe.</summary>
    public static byte[] Load(string wantSha, string embeddedSha)
    {
        try
        {
            string[] mark = File.ReadAllText(Mark(), Encoding.ASCII).Split('\n');
            if (mark.Length < 2) return null;
            // First line: what this cache is. Second: the exe's own copy at
            // the time it was written. If the exe has been replaced since,
            // the cache may well be OLDER than what is compiled in -- so it
            // is thrown away rather than trusted, which is what keeps
            // "prefer the cache" from being a way to go backwards.
            if (!string.Equals(mark[0].Trim(), wantSha, StringComparison.OrdinalIgnoreCase)) return null;
            if (embeddedSha != null &&
                !string.Equals(mark[1].Trim(), embeddedSha, StringComparison.OrdinalIgnoreCase)) return null;
            byte[] b = File.ReadAllBytes(Blob());
            using (SHA256 h = SHA256.Create())
            {
                StringBuilder sb = new StringBuilder();
                foreach (byte x in h.ComputeHash(b)) sb.Append(x.ToString("x2"));
                if (!string.Equals(sb.ToString(), wantSha, StringComparison.OrdinalIgnoreCase)) return null;
            }
            return b;
        }
        catch { return null; }
    }

    public static void Save(byte[] blob, string sha, string embeddedSha)
    {
        try
        {
            // Through a temporary file named after this process, so two
            // launchers started at once cannot write over each other
            // half-way. File.Replace wants the destination to exist and
            // File.Move wants it not to, hence both.
            string tmp = Path.Combine(Dir(), "texts." + Process().ToString() + ".tmp");
            File.WriteAllBytes(tmp, blob);
            string dest = Blob();
            try
            {
                if (File.Exists(dest)) File.Replace(tmp, dest, null);
                else File.Move(tmp, dest);
                File.WriteAllText(Mark(), sha + "\n" + (embeddedSha == null ? "" : embeddedSha),
                                  Encoding.ASCII);
            }
            finally
            {
                // Whatever went wrong, do not leave 1.9 MB behind: the cache is
                // written again on the next start, but nothing ever comes back
                // to sweep up a failed attempt.
                try { if (File.Exists(tmp)) File.Delete(tmp); }
                catch { }
            }
        }
        catch { /* a cache that cannot be written costs one download next time */ }
    }

    static int Process()
    {
        try { return System.Diagnostics.Process.GetCurrentProcess().Id; }
        catch { return 0; }
    }
}
