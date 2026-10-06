// The string table is the one file of a release that is not only shown but
// interpreted: its values reach TextField.htmlText. Checked before it is put
// in place, signature or not -- a defence that holds even on the day the
// resource key does not.
using System;
using System.Net;
using System.Text;

static class TextsCheck
{
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

    public static bool Sane(byte[] blob)
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

}
