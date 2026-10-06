// The documents of a client release, read and checked (client/FORMAT.md).
//
// Nothing here touches the network or the disk: bytes in, a verdict out. That
// is what lets launcher/test run every refusal below against documents that
// client/test_client.py's own code signed, so the two languages cannot drift
// apart on what "signed" means.
//
// THE SIGNATURE IS CHECKED BY HAND. RSACryptoServiceProvider.VerifyData with
// SHA-256 depends on which cryptographic provider the machine hands out, and
// on an old or oddly configured Windows that is the one without SHA-2 -- a
// launcher that cannot check a signature would have to choose between
// refusing every update and accepting any. RSASSA-PKCS1-v1_5 verification is
// one modular exponentiation and a byte comparison (RFC 8017, 8.2.2), and
// System.Numerics has the exponentiation on every .NET 4.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Numerics;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;

class ReleaseException : Exception
{
    public ReleaseException(string why) : base(why) { }
}

// The public keys compiled into this exe. Each string is one line of a .keys
// file: "<keyid> <e> <n in hex>".
class KeySet
{
    readonly Dictionary<string, BigInteger[]> keys = new Dictionary<string, BigInteger[]>();

    public int Count { get { return keys.Count; } }

    public KeySet(string[] lines)
    {
        foreach (string raw in lines)
        {
            string line = raw.Trim();
            if (line.Length == 0 || line.StartsWith("#")) continue;
            string[] p = line.Split(new char[] { ' ' }, StringSplitOptions.RemoveEmptyEntries);
            if (p.Length != 3) throw new ReleaseException("bad key line");
            BigInteger e = BigInteger.Parse(p[1], CultureInfo.InvariantCulture);
            byte[] nb = Hex.Decode((p[2].Length % 2 == 1 ? "0" : "") + p[2]);
            BigInteger n = Sig.ToInt(nb);
            if (Sig.KeyId(n) != p[0]) throw new ReleaseException("key id does not match its modulus");
            keys[p[0]] = new BigInteger[] { e, n };
        }
    }

    public bool TryGet(string id, out BigInteger e, out BigInteger n)
    {
        BigInteger[] v;
        if (keys.TryGetValue(id, out v)) { e = v[0]; n = v[1]; return true; }
        e = BigInteger.Zero; n = BigInteger.Zero;
        return false;
    }
}

static class Sig
{
    // DigestInfo for SHA-256 (RFC 8017, 9.2, note 1).
    static readonly byte[] PREFIX = Hex.Decode("3031300d060960864801650304020105000420");
    // \z, not $: in .NET $ also matches before a final newline.
    static readonly Regex LINE = new Regex("^sig ([0-9a-f]{16}) ([A-Za-z0-9+/]+={0,2})\n\\z");

    public static BigInteger ToInt(byte[] bigEndian)
    {
        byte[] le = new byte[bigEndian.Length + 1];          // + a zero: positive
        for (int i = 0; i < bigEndian.Length; i++) le[i] = bigEndian[bigEndian.Length - 1 - i];
        return new BigInteger(le);
    }

    static byte[] ToBytes(BigInteger v, int length)
    {
        byte[] le = v.ToByteArray();
        int n = le.Length;
        while (n > 0 && le[n - 1] == 0) n--;                   // the sign byte and leading zeros
        if (n > length) return null;
        byte[] be = new byte[length];
        for (int i = 0; i < n; i++) be[length - 1 - i] = le[i];
        return be;
    }

    static int Len(BigInteger n)
    {
        byte[] le = n.ToByteArray();
        int k = le.Length;
        while (k > 0 && le[k - 1] == 0) k--;
        return k;
    }

    public static string KeyId(BigInteger n)
    {
        return Hex.Encode(Hashes.Sha256(ToBytes(n, Len(n)))).Substring(0, 16);
    }

    public static bool Verify(BigInteger e, BigInteger n, byte[] data, byte[] sig)
    {
        int k = Len(n);
        if (sig.Length != k) return false;
        BigInteger s = ToInt(sig);
        if (s >= n) return false;
        byte[] em = ToBytes(BigInteger.ModPow(s, e, n), k);
        if (em == null) return false;
        byte[] t = new byte[PREFIX.Length + 32];
        Buffer.BlockCopy(PREFIX, 0, t, 0, PREFIX.Length);
        Buffer.BlockCopy(Hashes.Sha256(data), 0, t, PREFIX.Length, 32);
        if (k < t.Length + 11) return false;
        // 00 01 FF..FF 00 T, every byte of it.
        int ps = k - t.Length - 3, diff = 0;
        diff |= em[0];
        diff |= em[1] ^ 0x01;
        for (int i = 0; i < ps; i++) diff |= em[2 + i] ^ 0xFF;
        diff |= em[2 + ps];
        for (int i = 0; i < t.Length; i++) diff |= em[3 + ps + i] ^ t[i];
        return diff == 0;
    }

    /// <summary>The body of a signed document, if one of keys signed it.</summary>
    public static byte[] Open(KeySet keys, byte[] doc)
    {
        if (doc == null || doc.Length < 2 || doc[doc.Length - 1] != (byte)'\n')
            throw new ReleaseException("not a signed document");
        int cut = doc.Length - 1;
        while (cut > 0 && doc[cut - 1] != (byte)'\n') cut--;
        string last = Encoding.ASCII.GetString(doc, cut, doc.Length - cut);
        Match m = LINE.Match(last);
        if (!m.Success) throw new ReleaseException("no signature line");
        BigInteger e, n;
        if (!keys.TryGet(m.Groups[1].Value, out e, out n))
            throw new ReleaseException("signed by a key this launcher does not know (" + m.Groups[1].Value + ")");
        byte[] body = new byte[cut];
        Buffer.BlockCopy(doc, 0, body, 0, cut);
        byte[] sig;
        try { sig = Convert.FromBase64String(m.Groups[2].Value); }
        catch (FormatException) { throw new ReleaseException("signature is not base64"); }
        if (!Verify(e, n, body, sig)) throw new ReleaseException("signature does not match");
        return body;
    }
}

static class Hex
{
    public static string Encode(byte[] d)
    {
        StringBuilder sb = new StringBuilder(d.Length * 2);
        foreach (byte b in d) sb.Append(b.ToString("x2"));
        return sb.ToString();
    }

    public static byte[] Decode(string s)
    {
        if (s.Length % 2 != 0) throw new ReleaseException("odd hex");
        byte[] b = new byte[s.Length / 2];
        for (int i = 0; i < b.Length; i++)
            b[i] = byte.Parse(s.Substring(2 * i, 2), NumberStyles.HexNumber, CultureInfo.InvariantCulture);
        return b;
    }
}

static class Hashes
{
    // The provider rather than SHA256.Create(): on .NET 4 that is the managed
    // implementation, several times slower, and the first install hashes 2 GB.
    public static HashAlgorithm New()
    {
        try { return new SHA256CryptoServiceProvider(); }
        catch { return SHA256.Create(); }
    }

    public static byte[] Sha256(byte[] data)
    {
        using (HashAlgorithm h = New()) return h.ComputeHash(data);
    }

    public static string Sha256Hex(byte[] data) { return Hex.Encode(Sha256(data)); }

    public static string FileSha(string path, out long size)
    {
        using (HashAlgorithm h = New())
        using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read, FileShare.Read, 1 << 16))
        {
            size = fs.Length;
            return Hex.Encode(h.ComputeHash(fs));
        }
    }
}

class Pointer
{
    public long Serial;
    public string ManifestSha, ManifestPath;
    public long ManifestSize;
    public int LauncherVersion;                 // 0: none named
    public string LauncherSha, LauncherPath;
    public long LauncherSize;

    static readonly Regex RX = new Regex(
        "^lava-pointer 1\n" +
        "serial ([0-9]{1,15})\n" +
        "created \\S+\n" +
        "manifest ([0-9a-f]{64}) ([0-9]{1,12}) (manifests/[0-9]{1,15}\\.txt)\n" +
        "(?:launcher ([0-9]{1,9}) ([0-9a-f]{64}) ([0-9]{1,12}) (launcher/[0-9]{1,9}\\.exe)\n)?\\z");

    public static Pointer Read(KeySet keys, byte[] doc)
    {
        string body = Encoding.UTF8.GetString(Sig.Open(keys, doc));
        Match m = RX.Match(body);
        if (!m.Success) throw new ReleaseException("not a pointer");
        Pointer p = new Pointer();
        p.Serial = long.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture);
        p.ManifestSha = m.Groups[2].Value;
        p.ManifestSize = long.Parse(m.Groups[3].Value, CultureInfo.InvariantCulture);
        p.ManifestPath = m.Groups[4].Value;
        if (m.Groups[5].Success)
        {
            p.LauncherVersion = int.Parse(m.Groups[5].Value, CultureInfo.InvariantCulture);
            p.LauncherSha = m.Groups[6].Value;
            p.LauncherSize = long.Parse(m.Groups[7].Value, CultureInfo.InvariantCulture);
            p.LauncherPath = m.Groups[8].Value;
        }
        return p;
    }
}

class Statement
{
    public int Version;
    public string Sha;
    public long Size;

    static readonly Regex RX = new Regex(
        "^lava-launcher 1\nversion ([0-9]{1,9})\nsha256 ([0-9a-f]{64})\nsize ([0-9]{1,12})\ncreated \\S+\n\\z");

    public static Statement Read(KeySet keys, byte[] doc)
    {
        string body = Encoding.UTF8.GetString(Sig.Open(keys, doc));
        Match m = RX.Match(body);
        if (!m.Success) throw new ReleaseException("not a launcher statement");
        Statement s = new Statement();
        s.Version = int.Parse(m.Groups[1].Value, CultureInfo.InvariantCulture);
        s.Sha = m.Groups[2].Value;
        s.Size = long.Parse(m.Groups[3].Value, CultureInfo.InvariantCulture);
        return s;
    }
}

class Entry
{
    public string Sha;
    public long Size;
    public string Path;           // as the release spells it, with '/'
}

class Manifest
{
    public long Serial;
    public readonly List<Entry> Files = new List<Entry>();
    public long TotalBytes;
    // Windows does not tell a file from its name in another case, and Flash
    // asks for names in whatever case its code spells them.
    readonly Dictionary<string, Entry> byPath = new Dictionary<string, Entry>(StringComparer.OrdinalIgnoreCase);

    public Entry Find(string path)
    {
        Entry e;
        return byPath.TryGetValue(path, out e) ? e : null;
    }

    static readonly Regex HEAD = new Regex(
        "^lava-manifest 1\nserial ([0-9]{1,15})\nsource \\S+\nfiles ([0-9]{1,9}) ([0-9]{1,15})\n");
    static readonly Regex LINE = new Regex("^([0-9a-f]{64})\t([0-9]{1,12})\t([^\t\n]+)\\z");
    // The path rules of client/FORMAT.md, the same as client/build.py's
    // check_path: a whitelist of ASCII, so that the two languages cannot
    // disagree about case or length. Every name of the original fits it.
    static readonly Regex PART = new Regex("^[A-Za-z0-9 ._()-]+\\z");
    // Device names: "con.swf" opens the console, not a file, on Windows.
    static readonly Regex DEVICE = new Regex("^(con|prn|aux|nul|com[0-9]|lpt[0-9]|conin\\$|conout\\$)(\\..*)?\\z",
                                             RegexOptions.IgnoreCase | RegexOptions.CultureInvariant);
    public const int MAX_PATH_LEN = 150;

    public static bool PathOk(string p)
    {
        if (p.Length == 0 || p.Length > MAX_PATH_LEN) return false;
        string[] parts = p.Split('/');
        foreach (string s in parts)
        {
            if (s.Length == 0 || s == "." || s == ".." || !PART.IsMatch(s)) return false;
            // Windows trims these off a name on its own, and then two paths of
            // the release are one file on the disk.
            if (s.EndsWith(".", StringComparison.Ordinal) || s.EndsWith(" ", StringComparison.Ordinal)) return false;
            if (DEVICE.IsMatch(s)) return false;
        }
        return !string.Equals(parts[0], ".lava", StringComparison.OrdinalIgnoreCase);
    }

    /// <summary>The manifest in data, which the caller has already matched
    /// against the hash a signed pointer gives for it.</summary>
    public static Manifest Read(byte[] data)
    {
        string text;
        try { text = new UTF8Encoding(false, true).GetString(data); }
        catch (ArgumentException) { throw new ReleaseException("manifest is not UTF-8"); }
        Match h = HEAD.Match(text);
        if (!h.Success) throw new ReleaseException("not a manifest");
        Manifest m = new Manifest();
        m.Serial = long.Parse(h.Groups[1].Value, CultureInfo.InvariantCulture);
        int count = int.Parse(h.Groups[2].Value, CultureInfo.InvariantCulture);
        long total = long.Parse(h.Groups[3].Value, CultureInfo.InvariantCulture);
        if (!text.EndsWith("\n", StringComparison.Ordinal) || text.Length <= h.Length)
            throw new ReleaseException("manifest is cut short or lists no files");
        string[] lines = text.Substring(h.Length, text.Length - h.Length - 1).Split('\n');
        byte[] prev = null;
        foreach (string line in lines)
        {
            Match l = LINE.Match(line);
            if (!l.Success) throw new ReleaseException("bad manifest line");
            Entry e = new Entry();
            e.Sha = l.Groups[1].Value;
            e.Size = long.Parse(l.Groups[2].Value, CultureInfo.InvariantCulture);
            e.Path = l.Groups[3].Value;
            if (!PathOk(e.Path)) throw new ReleaseException("manifest names a path it may not: " + e.Path);
            byte[] key = Encoding.UTF8.GetBytes(e.Path);
            if (prev != null && Compare(prev, key) >= 0) throw new ReleaseException("manifest is not sorted");
            prev = key;
            if (m.byPath.ContainsKey(e.Path)) throw new ReleaseException("two paths differ only in case: " + e.Path);
            m.byPath[e.Path] = e;
            m.Files.Add(e);
            m.TotalBytes += e.Size;
        }
        if (m.Files.Count != count || m.TotalBytes != total)
            throw new ReleaseException("manifest does not add up");
        // A file cannot also be a folder of another file.
        foreach (Entry e in m.Files)
        {
            int at = 0;
            while ((at = e.Path.IndexOf('/', at)) > 0)
            {
                if (m.byPath.ContainsKey(e.Path.Substring(0, at)))
                    throw new ReleaseException("a file is also a folder: " + e.Path.Substring(0, at));
                at++;
            }
        }
        return m;
    }

    static int Compare(byte[] a, byte[] b)
    {
        int n = Math.Min(a.Length, b.Length);
        for (int i = 0; i < n; i++) if (a[i] != b[i]) return a[i] - b[i];
        return a.Length - b.Length;
    }
}
