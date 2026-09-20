// Asking the game server the two questions the window needs answered:
// is it there, and is this password right.
//
// Both are asked over the game socket itself, with the client's own
// handshake -- hello, login, cmdAck -- because that is the only authority on
// either. No new endpoint, no second copy of the rules, and the answer the
// launcher shows is the answer the client would have got.
//
// The probe logs in and leaves without selecting a character, so it never
// touches the world: server.py has no objection to a second session on one
// account, and Session.close() on a session that picked nobody does nothing.
using System;
using System.Collections.Generic;
using System.IO;
using System.Net.Sockets;
using System.Text;

enum Verdict
{
    Ok,
    BadCredentials,
    Banned,
    Unreachable,
    Unexpected,
}

static class GameProbe
{
    const int ConnectMs = 6000;
    const int ReadMs = 12000;

    // Frame: "<name>;<key>=<value>;" terminated by NUL, UTF-8 (protocol.py).
    static void Send(NetworkStream s, string frame)
    {
        byte[] b = Encoding.UTF8.GetBytes(frame);
        s.Write(b, 0, b.Length);
        s.WriteByte(0);
        s.Flush();
    }

    static string Read(NetworkStream s)
    {
        MemoryStream buf = new MemoryStream();
        while (true)
        {
            int c = s.ReadByte();
            if (c < 0) return null;          // closed under us
            if (c == 0) break;
            buf.WriteByte((byte)c);
        }
        return Encoding.UTF8.GetString(buf.ToArray());
    }

    static string Name(string frame)
    {
        int i = frame.IndexOf(';');
        return i < 0 ? frame : frame.Substring(0, i);
    }

    static Dictionary<string, string> Params(string frame)
    {
        Dictionary<string, string> d = new Dictionary<string, string>();
        string[] parts = frame.Split(';');
        for (int i = 1; i < parts.Length; i++)
        {
            int eq = parts[i].IndexOf('=');
            if (eq <= 0) continue;
            d[parts[i].Substring(0, eq)] = parts[i].Substring(eq + 1);
        }
        return d;
    }

    static TcpClient Open(string host, int port)
    {
        TcpClient c = new TcpClient();
        IAsyncResult ar = c.BeginConnect(host, port, null, null);
        if (!ar.AsyncWaitHandle.WaitOne(ConnectMs, false))
        {
            try { c.Close(); } catch { }
            return null;
        }
        try { c.EndConnect(ar); }
        catch { try { c.Close(); } catch { } return null; }
        c.NoDelay = true;
        return c;
    }

    // The status line: the server answers hello, or it does not.
    public static bool Ping(string host, int port)
    {
        TcpClient c = null;
        try
        {
            c = Open(host, port);
            if (c == null) return false;
            NetworkStream s = c.GetStream();
            s.ReadTimeout = ReadMs;
            s.WriteTimeout = ReadMs;
            Send(s, "hello;minor=2;major=0;");
            string frame = Read(s);
            return frame != null && Name(frame) == "hello";
        }
        catch { return false; }
        finally { if (c != null) try { c.Close(); } catch { } }
    }

    public static Verdict Check(string host, int port, string hash)
    {
        TcpClient c = null;
        try
        {
            c = Open(host, port);
            if (c == null) return Verdict.Unreachable;
            NetworkStream s = c.GetStream();
            s.ReadTimeout = ReadMs;
            s.WriteTimeout = ReadMs;

            Send(s, "hello;minor=2;major=0;");
            string frame = Read(s);
            if (frame == null) return Verdict.Unreachable;
            if (Name(frame) != "hello") return Verdict.Unexpected;

            Send(s, "login;hash=@" + hash + "@;");

            // cmdAck is first, but the server follows it with the account's
            // state without being asked, so read until the acknowledgement
            // rather than assuming it is frame one.
            for (int i = 0; i < 16; i++)
            {
                frame = Read(s);
                if (frame == null) return Verdict.Unexpected;
                if (Name(frame) != "cmdAck") continue;

                string res;
                if (!Params(frame).TryGetValue("res", out res)) return Verdict.Unexpected;
                try { Send(s, "logout;"); } catch { }
                switch (res)
                {
                    case "0": return Verdict.Ok;
                    case "1": return Verdict.BadCredentials;
                    case "2": return Verdict.Banned;
                    default: return Verdict.Unexpected;
                }
            }
            return Verdict.Unexpected;
        }
        catch (IOException) { return Verdict.Unreachable; }
        catch (SocketException) { return Verdict.Unreachable; }
        catch { return Verdict.Unexpected; }
        finally { if (c != null) try { c.Close(); } catch { } }
    }
}
