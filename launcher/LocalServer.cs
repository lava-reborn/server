// A web server on the loopback, serving the installed release to the
// player's own Flash.
//
// Only the files the release lists, and each one hashed as it goes out
// (Sync.Serve): a name the release does not hold is a 404 whatever lies on
// the disk under it, and a file changed on the disk since the check is
// mended from the store before Flash sees a byte of it.
//
// Why a client needs a web server at all: the client only skips its login
// screen along one path, and that path is HTTP. Session.loadSBase
// (lol/core/Session.as:88) takes it when _root.logged == 1 and
// SSEmulator.PATHTYPE == WEB, and then POSTs to the root-relative
// /exe/lavaclient/loaduser/?ajax and logs in with whatever host, port and
// hash come back. A movie opened off the disk has no origin for that URL to
// be relative to, so there is nothing to answer it -- and PATHTYPE is only
// WEB when xmldocs/csettings_v1.xml loads, which is the other half of the
// same trick. Serving both from 127.0.0.1 gives the client the one thing it
// wants and costs the player nothing: every byte comes off their own disk and
// none of it leaves the machine.
//
// The routes are the ones server/bootstrap_http.py already answers for the
// owner's own ./run.sh, deliberately: that mapping is proven against the real
// projector, and WEB paths are the LOCAL paths with a base glued in front
// (SSEmulator.getStringURL and friends), so /res/<x> is <res>/<x> and nothing
// more clever is needed.
using System;
using System.Collections.Generic;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

class LocalServer
{
    readonly Sync sync;            // the release, and the only way to its files
    readonly Manifest release;     // what this game is played with, fixed at start
    readonly byte[] wrapper;       // the film that loads the game (16:9 or plain), or null
    readonly string gameHost;
    readonly int gamePort;
    TcpListener listener;
    volatile bool running;

    // Set the moment the credential is known and before the game starts. Null
    // until then, and the client is never pointed here before it is set.
    public volatile string Hash;

    public int Port { get; private set; }

    // Raised on the first request for a location, which is the client leaving
    // the loading screen and building the world. The window waits for it.
    public event Action WorldLoading;
    int worldSignalled;

    // When the client last asked for anything. Quiet here means it has
    // finished putting the world together, which is a better moment to show
    // the game than any number of seconds guessed in advance.
    public volatile int LastRequest;

    public LocalServer(Sync sync, byte[] wrapperSwf, string host, int port)
    {
        this.sync = sync;
        release = sync.Current;
        if (release == null) throw new InvalidOperationException("игра не установлена");
        wrapper = wrapperSwf;
        gameHost = host;
        gamePort = port;
    }

    public void Start()
    {
        // Port 0: the operating system picks a free one. A fixed port would
        // collide with whatever else the player runs, and nothing outside
        // this process needs to know the number.
        listener = new TcpListener(IPAddress.Loopback, 0);
        listener.Start();
        Port = ((IPEndPoint)listener.LocalEndpoint).Port;
        running = true;
        Thread t = new Thread(Accept);
        t.IsBackground = true;
        t.Name = "lava-http";
        t.Start();
    }

    public void Stop()
    {
        running = false;
        try { if (listener != null) listener.Stop(); }
        catch { }
    }

    public string MovieUrl()
    {
        // logged=1 is the whole point: without it the client shows its own
        // login window and never asks loaduser anything.
        //
        // The projector is pointed at our wrapper rather than at the game:
        // the 16:9 one because the game fixes the stage at 950x650 and
        // forbids scaling, the plain one because it is the only way to run
        // our ClanInspector mend inside the client (see tools/make_wrapper.py;
        // either film is served here under the one name). The wrapper lives at the same /res/
        // as the game, so every relative path the client builds -- above all
        // xmldocs/csettings_v1.xml, which is what puts it in WEB mode --
        // resolves exactly as it would have.
        string movie = wrapper != null ? "wrapper.swf" : "main.swf";
        return "http://127.0.0.1:" + Port + "/res/" + movie + "?logged=1&vversion=1"
             + "&var_host=" + gameHost + "&var_port=" + gamePort;
    }

    void Accept()
    {
        while (running)
        {
            TcpClient c;
            try { c = listener.AcceptTcpClient(); }
            catch { return; }                     // Stop() closed the listener
            ThreadPool.QueueUserWorkItem(Serve, c);
        }
    }

    void Serve(object state)
    {
        TcpClient c = (TcpClient)state;
        try
        {
            c.NoDelay = true;
            using (NetworkStream net = c.GetStream())
            using (BufferedStream inp = new BufferedStream(net, 8192))
            {
                net.ReadTimeout = 30000;
                net.WriteTimeout = 30000;
                // Keep-alive: Flash asks for thousands of files and a fresh
                // connection for each one is the difference between a world
                // that opens and one that crawls.
                while (running && Handle(inp, net)) { }
            }
        }
        catch { /* the client hung up; nothing here is worth reporting */ }
        finally { try { c.Close(); } catch { } }
    }

    // Returns true if the connection may be reused.
    bool Handle(Stream inp, Stream outp)
    {
        string line = ReadLine(inp);
        if (string.IsNullOrEmpty(line)) return false;

        string[] parts = line.Split(' ');
        if (parts.Length < 2) return false;
        string method = parts[0];
        string target = parts[1];
        bool keep = parts.Length < 3 || parts[2].IndexOf("1.1", StringComparison.Ordinal) >= 0;

        int length = 0;
        string host = null;
        while (true)
        {
            string h = ReadLine(inp);
            if (h == null) return false;
            if (h.Length == 0) break;
            if (h.StartsWith("Content-Length:", StringComparison.OrdinalIgnoreCase))
                int.TryParse(h.Substring(15).Trim(), out length);
            else if (h.StartsWith("Host:", StringComparison.OrdinalIgnoreCase))
                host = h.Substring(5).Trim();
            else if (h.StartsWith("Connection:", StringComparison.OrdinalIgnoreCase) &&
                     h.IndexOf("close", StringComparison.OrdinalIgnoreCase) >= 0)
                keep = false;
        }

        // Only this machine's own names. A web page that points a name of its
        // own at 127.0.0.1 (DNS rebinding) reaches this port with that name in
        // Host, and must not read loaduser's answer -- the account's hash.
        if (host != null &&
            !string.Equals(host, "127.0.0.1:" + Port, StringComparison.OrdinalIgnoreCase) &&
            !string.Equals(host, "localhost:" + Port, StringComparison.OrdinalIgnoreCase))
        {
            Send(outp, 403, "text/plain", Encoding.UTF8.GetBytes("forbidden"), false);
            return false;
        }

        // The body has to be drained even when it is ignored, or the next
        // request on this connection starts mid-sentence. The client posts
        // for most XML: LoadVars.sendAndLoad and XML.sendAndLoad are both
        // POST, and real Flash downgrades to GET only when there is nothing
        // to send. Method therefore decides nothing here.
        while (length > 0)
        {
            byte[] skip = new byte[Math.Min(length, 8192)];
            int n = inp.Read(skip, 0, skip.Length);
            if (n <= 0) break;
            length -= n;
        }

        string path = target;
        int q = path.IndexOf('?');
        string query = q >= 0 ? path.Substring(q + 1) : "";
        if (q >= 0) path = path.Substring(0, q);
        try { path = Uri.UnescapeDataString(path); }
        catch { }

        Route(method, path, query, outp, keep);
        return keep;
    }

    void Route(string method, string path, string query, Stream outp, bool keep)
    {
        LastRequest = Environment.TickCount;
        Log.Hit(method, path, query);

        if (path.StartsWith("/exe/lavaclient/loaduser", StringComparison.OrdinalIgnoreCase))
        {
            // Session.getHashHostPort reads "<host>:<port> <hash>": host up to
            // the colon, port up to the first space after it, the digest after
            // that. Sent raw -- a value with no percent signs survives
            // LoadVars' unescape either way, and this way it survives a
            // player that does not unescape at all.
            string h = Hash;
            string body = gameHost + ":" + gamePort + (string.IsNullOrEmpty(h) ? "" : " " + h);
            Send(outp, 200, "application/x-www-form-urlencoded",
                 Encoding.UTF8.GetBytes("data=" + body), keep);
            return;
        }

        if (path.EndsWith("/crossdomain.xml", StringComparison.OrdinalIgnoreCase))
        {
            Send(outp, 200, "text/x-cross-domain-policy", Encoding.UTF8.GetBytes(
                "<?xml version=\"1.0\"?><cross-domain-policy>" +
                "<allow-access-from domain=\"*\" to-ports=\"*\"/>" +
                "</cross-domain-policy>"), keep);
            return;
        }

        if (!path.StartsWith("/res/", StringComparison.OrdinalIgnoreCase))
        {
            NotFound(outp, path, keep);
            return;
        }

        string rel = path.Substring(5);

        // The three documents the shipped client does not have. csettings is
        // what flips the client into WEB mode at all, so it is first.
        if (rel.Equals("xmldocs/csettings_v1.xml", StringComparison.OrdinalIgnoreCase))
        {
            Send(outp, 200, "text/xml", Encoding.UTF8.GetBytes(Csettings()), keep);
            return;
        }
        if (wrapper != null
            && rel.Equals("wrapper.swf", StringComparison.OrdinalIgnoreCase))
        {
            // Carried in the exe and served from memory; not a file of the
            // release.
            Send(outp, 200, "application/x-shockwave-flash", wrapper, keep);
            return;
        }

        // Everything else is a file of the release or nothing. The string
        // table, hints.xml and the map's names are files of the release too:
        // the server builds them into it (client/build.py), so they are
        // installed, checked and served like any other.
        Entry e = release.Find(rel);
        if (e == null)
        {
            if (rel.Equals("hints/hints.xml", StringComparison.OrdinalIgnoreCase))
            {
                // A release from before hints.xml was in it. Empty is fine --
                // it costs the tooltips -- but UTF-8 with a mark, like every
                // other XML the client reads.
                byte[] doc = Encoding.UTF8.GetBytes("﻿<?xml version='1.0'?><data/>");
                Send(outp, 200, "text/xml; charset=utf-8", doc, keep);
                return;
            }
            NotFound(outp, rel + " (нет в релизе)", keep);
            return;
        }

        if (rel.StartsWith("locations/", StringComparison.OrdinalIgnoreCase) &&
            Interlocked.Exchange(ref worldSignalled, 1) == 0)
        {
            Action f = WorldLoading;
            if (f != null) try { f(); } catch { }
        }

        byte[] served = sync.Serve(e);
        if (served == null)
        {
            NotFound(outp, rel + " (не сошёлся по хэшу и не восстановлен)", keep);
            return;
        }
        Send(outp, 200, Mime(rel), served, keep);
    }

    string Csettings()
    {
        // base has no trailing slash: the client builds "base + /database/..."
        // (SSEmulator.getStringURL and the rest), and two slashes there are a
        // 404 on some of these paths.
        return
            "<?xml version=\"1.0\" encoding=\"utf-8\"?>\r\n" +
            "<settings>\r\n" +
            "  <gamesrv host=\"" + gameHost + "\" port=\"" + gamePort + "\"/>\r\n" +
            "  <debug value=\"0\"/>\r\n" +
            "  <resource base=\"http://127.0.0.1:" + Port + "/res\">\r\n" +
            "    <item_icon format=\"swf\">classes/</item_icon>\r\n" +
            "    <item_anim format=\"swf\">classes/</item_anim>\r\n" +
            "    <avatar_list format=\"xml\">avatars/list.xml</avatar_list>\r\n" +
            "    <avatar format=\"swf\">avatars/</avatar>\r\n" +
            "    <sprite format=\"swf\">locations/libs/</sprite>\r\n" +
            "    <globalmap format=\"swf\">globalmap/</globalmap>\r\n" +
            "    <location_info format=\"xml\">locations/</location_info>\r\n" +
            "    <location_lib format=\"swf\">locations/libs/</location_lib>\r\n" +
            "    <mob_anim format=\"swf\">mobs/</mob_anim>\r\n" +
            "    <mob_info format=\"xml\">mobs/</mob_info>\r\n" +
            "    <char_anim format=\"swf\">personages/</char_anim>\r\n" +
            "    <char_info format=\"xml\">personages/</char_info>\r\n" +
            "    <text format=\"xml\">xmldocs/</text>\r\n" +
            "    <sound format=\"swf\">sounds/</sound>\r\n" +
            "  </resource>\r\n" +
            "</settings>\r\n";
    }

    static readonly Dictionary<string, string> Types = Mimes();

    static Dictionary<string, string> Mimes()
    {
        Dictionary<string, string> d = new Dictionary<string, string>(StringComparer.OrdinalIgnoreCase);
        d[".swf"] = "application/x-shockwave-flash";
        d[".xml"] = "text/xml";
        d[".jpg"] = "image/jpeg";
        d[".jpeg"] = "image/jpeg";
        d[".png"] = "image/png";
        d[".gif"] = "image/gif";
        d[".mp3"] = "audio/mpeg";
        d[".txt"] = "text/plain";
        return d;
    }

    static string Mime(string path)
    {
        string ext = Path.GetExtension(path);
        string t;
        return Types.TryGetValue(ext == null ? "" : ext, out t)
             ? t : "application/octet-stream";
    }

    void NotFound(Stream outp, string what, bool keep)
    {
        Log.Miss(what);
        Send(outp, 404, "text/plain", Encoding.UTF8.GetBytes("not found"), keep);
    }

    static byte[] Head(int code, string type, long length, bool keep)
    {
        StringBuilder sb = new StringBuilder();
        sb.Append("HTTP/1.1 ").Append(code)
          .Append(code == 200 ? " OK" : code == 403 ? " Forbidden" : " Not Found").Append("\r\n");
        sb.Append("Content-Type: ").Append(type).Append("\r\n");
        sb.Append("Content-Length: ").Append(length).Append("\r\n");
        sb.Append("Cache-Control: no-store\r\n");
        sb.Append("Connection: ").Append(keep ? "keep-alive" : "close").Append("\r\n\r\n");
        return Encoding.ASCII.GetBytes(sb.ToString());
    }

    // Header and body go out in one write. Two writes are two packets, and on
    // a keep-alive connection that is a delayed acknowledgement per file --
    // across the thousands of files a world is made of, it is the difference
    // between loading and crawling.
    static void Send(Stream outp, int code, string type, byte[] body, bool keep)
    {
        byte[] head = Head(code, type, body.Length, keep);
        byte[] all = new byte[head.Length + body.Length];
        Buffer.BlockCopy(head, 0, all, 0, head.Length);
        Buffer.BlockCopy(body, 0, all, head.Length, body.Length);
        outp.Write(all, 0, all.Length);
        outp.Flush();
    }

    static string ReadLine(Stream s)
    {
        StringBuilder sb = new StringBuilder(128);
        while (true)
        {
            int c = s.ReadByte();
            if (c < 0) return sb.Length == 0 ? null : sb.ToString();
            if (c == '\n') return sb.ToString().TrimEnd('\r');
            sb.Append((char)c);
            if (sb.Length > 8192) return null;
        }
    }
}

// A 404 on a resource is a black screen with no error anywhere in the client,
// so the misses are worth writing down. Nothing else is logged: a working
// session should leave an empty file.
static class Log
{
    static readonly object gate = new object();
    static int written;

    // LAVA_LOG_DIR moves both files, so launcher/test leaves a player's own
    // log alone.
    static string Dir()
    {
        string d = Environment.GetEnvironmentVariable("LAVA_LOG_DIR");
        return string.IsNullOrEmpty(d)
            ? System.IO.Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "LavaOnline")
            : d;
    }

    public static string Path
    {
        get { return System.IO.Path.Combine(Dir(), "missing.log"); }
    }

    // Every request, not only the ones that failed. A client that hangs
    // without asking for anything and a client that asked for the wrong
    // thing look identical from outside, and the difference is the whole
    // diagnosis. Switched on by LAVA_HTTPLOG=1; off, this costs one
    // comparison per request.
    static readonly bool Verbose = IsOn("LAVA_HTTPLOG");
    static int hits;

    static bool IsOn(string name)
    {
        string v = Environment.GetEnvironmentVariable(name);
        if (v == null) return false;
        v = v.Trim().ToLowerInvariant();
        return v != "" && v != "0" && v != "no" && v != "off" && v != "false";
    }

    public static string HitPath
    {
        get { return System.IO.Path.Combine(Dir(), "http.log"); }
    }

    public static void Hit(string method, string path, string query)
    {
        if (!Verbose) return;
        lock (gate)
        {
            if (hits > 4000) return;
            hits++;
            try
            {
                System.IO.File.AppendAllText(HitPath,
                    DateTime.Now.ToString("HH:mm:ss.fff") + "  " + method + " " + path
                    + (string.IsNullOrEmpty(query) ? "" : "?" + query) + "\r\n");
            }
            catch { }
        }
    }

    public static void Miss(string what)
    {
        lock (gate)
        {
            if (written > 500) return;            // a broken res/ is not a diary
            written++;
            try
            {
                System.IO.File.AppendAllText(Path,
                    DateTime.Now.ToString("HH:mm:ss") + "  " + what + "\r\n");
            }
            catch { }
        }
    }

    public static void Start()
    {
        lock (gate)
        {
            written = 0;
            hits = 0;
            try { System.IO.File.Delete(Path); }
            catch { }
            try { System.IO.File.Delete(HitPath); }
            catch { }
        }
    }
}
