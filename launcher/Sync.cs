// Keeping the game folder exactly what the published release says it is.
//
// The launcher owns the folder it sits in: res/ beside the exe is the game,
// installed and kept by this file, and .lava/ beside it is this file's
// memory. On every start, on its own thread, while the player reads the
// window:
//
//   1. fetch ROOT/current.txt and check its signature (resource key) and that
//      its serial is not older than any accepted before;
//   2. if it names a newer launcher, fetch that, check it against a statement
//      signed with the launcher key, swap the exe and ask to be restarted;
//   3. fetch the manifest it names (checked by the hash in the pointer);
//   4. look at every file the manifest lists: size and modification time
//      against .lava/index.tsv, and a full hash for anything the index does
//      not vouch for;
//   5. download what is missing or different, hash every byte on the way
//      in, and only then put it in place, one file at a time, atomically;
//   6. remember the accepted pointer, manifest and index.
//
// While the game runs, LocalServer hands Flash only files the manifest lists,
// and hashes each one as it serves it (Serve below): a file changed on the
// disk after the check is mended from the store, never handed over.
//
// Client/FORMAT.md is the other half of every rule here.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Cache;
using System.Text;
using System.Threading;

enum SyncState
{
    Checking,      // asking the server
    Scanning,      // hashing files the index does not vouch for
    Downloading,   // fetching files
    Restarting,    // a new launcher is in place; restart into it
    MustUpdate,    // a new launcher exists and could not be put in place
    Ready,         // the folder is the published release
    Offline,       // the server could not be asked; the folder is the last accepted release
    Failed,        // there is nothing playable here
    Setup,         // nothing installed, AskFirst set: waiting for Begin()
    Paused,        // a download stopped by Pause(); what is staged is kept
    NoSpace,       // the drive cannot take what the download needs
}

// What a Failed run ran into, for the window to name: the line under it is
// the note, the title comes from this.
enum SyncFailure
{
    Other,         // the folder, the path, a refused release
    Network,       // a download that could not be completed
    Corrupt,       // a file that came down and did not match its hash
}

// Why an Offline run plays the installed release instead of the published
// one, for the window to name.
enum OfflineCause
{
    Unreachable,   // the update server did not answer
    Refused,       // what it offered failed the signature or is older than ours
    Download,      // the update did not come down whole
    Launcher,      // a new launcher exists and could not be put in place
}

// What a look at the published pointer found (Sync.Peek).
enum Peeked
{
    Unknown,       // no answer in time, or no pointer that verifies: nothing to go on
    Current,       // nothing newer than the serial Peek compares with
    Newer,         // a signed release newer than that: a run should take it
    Busy,          // a run is under way, and it is the one that looks
}

class Sync
{
    readonly string root;                  // the update root, with its trailing slash
    readonly string gameDir, resDir, stateDir, stagingDir;
    readonly KeySet resourceKeys, launcherKeys;
    readonly int myVersion;
    readonly string exePath;               // null: never replace the exe (tests)
    public bool FullVerify;                // --verify: hash every file, trust no index
    public string ManualUrl = "";          // where a player downloads the launcher by hand
    // Ask before a first install: the run stops at Setup with the size of
    // the download, and Begin() goes on. A folder that already holds a game
    // is updated without asking, as before.
    public bool AskFirst;

    readonly object gate = new object();
    SyncState state = SyncState.Checking;
    string note = "Проверяем обновления";
    long doneBytes, totalBytes;
    int doneFiles, totalFiles;
    int lastNotify;
    Manifest manifest;
    Index index;
    readonly ManualResetEvent settled = new ManualResetEvent(false);
    bool confirmed;                        // Begin() was pressed for this folder
    volatile bool pausing;                 // Pause() asked the download to stop
    bool fresh;                            // the run found no game in res/
    long needBytes, freeBytes;
    SyncFailure failure;
    OfflineCause offline;
    Pointer pointer;                       // the release in place: the pointer this folder last accepted
    string source;                         // and the commit its manifest names
    int updated;                           // files the last run put in place, if it ended Ready
    long seen;                             // the newest serial a run here accepted or was offered, signed
    long kept;                             // the newest this folder accepted, or could not take for want of a launcher
    const long SPARE = 64L * 1024 * 1024;  // headroom asked of the drive beyond the download
    const string PAUSED = "paused";
    const string HASH_MISMATCH = "файл не сошёлся по хэшу";
    const string TOO_LONG = "файл длиннее обещанного";
    const string TOO_SHORT = "файл короче обещанного";

    public Action Changed;                 // raised on the worker thread; the UI marshals it
    public int NewVersion;                 // set with Restarting

    const int TIMEOUT_MS = 30000;
    const int WORKERS = 6;
    const int TRIES = 4;

    public Sync(string gameDir, string root, KeySet resourceKeys, KeySet launcherKeys,
                int myVersion, string exePath)
    {
        this.gameDir = Path.GetFullPath(gameDir).TrimEnd(Path.DirectorySeparatorChar);
        this.root = root.EndsWith("/") ? root : root + "/";
        this.resDir = Path.Combine(this.gameDir, "res");
        this.stateDir = Path.Combine(this.gameDir, ".lava");
        this.stagingDir = Path.Combine(stateDir, "staging");
        this.resourceKeys = resourceKeys;
        this.launcherKeys = launcherKeys;
        this.myVersion = myVersion;
        this.exePath = exePath;
    }

    public string ResDir { get { return resDir; } }
    public SyncState State { get { lock (gate) return state; } }
    public string Note { get { lock (gate) return note; } }
    public Manifest Current { get { lock (gate) return manifest; } }
    /// <summary>The signed pointer of the release this folder holds, as it
    /// last accepted it: read back from .lava/ and verified at the start of
    /// a run, then the one the run accepted. When the release was published,
    /// for the window to say; null until a run has read one.</summary>
    public Pointer Accepted { get { lock (gate) return pointer; } }
    /// <summary>The commit that release was built from (its manifest's
    /// source), or null.</summary>
    public string AcceptedSource { get { lock (gate) return source; } }
    /// <summary>How many files the last run put in place, if it ended Ready
    /// (0 when it found every file as the release has it).</summary>
    public int Updated { get { lock (gate) return updated; } }
    /// <summary>Whether a run is under way, Start to settle.</summary>
    public bool Running { get { return Interlocked.CompareExchange(ref running, 0, 0) != 0; } }
    public bool Playable { get { SyncState s = State; return s == SyncState.Ready || s == SyncState.Offline; } }
    /// <summary>Whether the last run started on a folder with no game:
    /// an install, as against an update.</summary>
    public bool Fresh { get { lock (gate) return fresh; } }
    public long NeedBytes { get { lock (gate) return needBytes; } }
    public long FreeBytes { get { lock (gate) return freeBytes; } }
    public SyncFailure Failure { get { lock (gate) return failure; } }
    public OfflineCause Cause { get { lock (gate) return offline; } }
    public string GameDir { get { return gameDir; } }

    /// <summary>"Начать загрузку": the install AskFirst stopped at goes on.</summary>
    public void Begin()
    {
        lock (gate) confirmed = true;
        Start();
    }

    /// <summary>Stops a download between blocks. What is fully staged stays
    /// and is not fetched again; Start() goes on from there.</summary>
    public void Pause()
    {
        if (State == SyncState.Downloading) pausing = true;
    }

    /// <summary>Stops the run at its next safe point, whatever it is doing:
    /// a download between blocks, a check before anything is fetched. For
    /// the window moving the folder away under it.</summary>
    public void Hold()
    {
        if (Interlocked.CompareExchange(ref running, 0, 0) != 0) pausing = true;
    }

    public void Progress(out long done, out long total, out int files, out int fileTotal)
    {
        lock (gate) { done = doneBytes; total = totalBytes; files = doneFiles; fileTotal = totalFiles; }
    }

    void Move(SyncState s, string text)
    {
        lock (gate) { state = s; note = text; }
        Raise();
    }

    void Raise()
    {
        Action a = Changed;
        if (a != null) try { a(); } catch { }
    }

    // Progress changes thousands of times; the window needs a few a second.
    void Tick()
    {
        int now = Environment.TickCount;
        if (now - lastNotify < 200) return;
        lastNotify = now;
        Raise();
    }

    int running;

    /// <summary>Starts a run unless one is already going: a second click on
    /// "Повторить" must not start a second run over the same folder.</summary>
    public void Start()
    {
        if (Interlocked.CompareExchange(ref running, 1, 0) != 0) return;
        settled.Reset();
        pausing = false;
        lock (gate) failure = SyncFailure.Other;
        Thread t = new Thread(delegate ()
        {
            try { Run(); }
            catch (Exception e) { Move(SyncState.Failed, Short(e)); }
            // --verify and "Проверить файлы" are one run each; the next
            // goes back to trusting the index.
            finally { FullVerify = false; Interlocked.Exchange(ref running, 0); }
            settled.Set();
            Raise();
        });
        t.IsBackground = true;
        t.Name = "lava-sync";
        t.Start();
    }

    public bool Wait(int millis)
    {
        try { return settled.WaitOne(millis); }
        catch { return true; }
    }

    // --- the run -------------------------------------------------------------------

    void Run()
    {
        Tls();
        try
        {
            Directory.CreateDirectory(resDir);
            Directory.CreateDirectory(stagingDir);
        }
        catch (Exception e)
        {
            Move(SyncState.Failed, "Папка игры закрыта на запись (" + Short(e) + "). " +
                 "Перенесите лаунчер в свою папку, например на рабочий стол, и запустите снова.");
            return;
        }
        index = Index.Load(Path.Combine(stateDir, "index.tsv"));
        lock (gate) { fresh = !File.Exists(Path.Combine(resDir, "main.swf")); updated = 0; }

        // What this folder last accepted, re-checked: a file someone edited
        // in .lava/ is no better than one fetched from a stranger.
        Pointer local = null;
        Manifest localM = null;
        byte[] localDoc = ReadState("current.txt");
        if (localDoc != null)
        {
            try
            {
                local = Pointer.Read(resourceKeys, localDoc);
                byte[] md = ReadState("manifest.txt");
                if (md != null && md.LongLength == local.ManifestSize &&
                    Hashes.Sha256Hex(md) == local.ManifestSha)
                    localM = Manifest.Read(md);
            }
            catch (Exception) { local = null; localM = null; }
        }
        long highest = ReadHighest();
        if (local != null && local.Serial > highest) highest = local.Serial;
        lock (gate)
        {
            seen = Math.Max(seen, highest);
            kept = Math.Max(kept, highest);
            // The window names the release in place from here on, not only
            // once a run has ended Ready: a run that stops short of it
            // (Failed, NoSpace, Paused) leaves the installed game as it was.
            if (local != null) { pointer = local; source = localM != null ? localM.Source : null; }
        }

        Move(SyncState.Checking, "Проверяем обновления");
        Pointer remote = null;
        byte[] remoteDoc = null;
        string why = null;
        OfflineCause cause = OfflineCause.Refused;
        try
        {
            remoteDoc = Fetch(root + "current.txt?t=" + DateTime.UtcNow.Ticks, 64 * 1024);
            if (remoteDoc == null) { why = "сервер обновлений не ответил"; cause = OfflineCause.Unreachable; }
            else
            {
                remote = Pointer.Read(resourceKeys, remoteDoc);
                // Offered and signed, taken or not: the watch's Peek does not
                // call the window back for a release a run has been through.
                lock (gate) seen = Math.Max(seen, remote.Serial);
                if (remote.Serial < highest)
                {
                    why = "сервер предложил релиз старше уже установленного";
                    remote = null;
                }
            }
        }
        catch (ReleaseException e) { why = "обновление не прошло проверку подписи: " + e.Message; remote = null; }

        if (remote == null)
        {
            // Nothing new can be trusted. The folder as last accepted is still
            // the game, if every file of it is still what it was.
            if (!PlayLocal(local, localM, cause, "Обновления проверить не удалось (" + why + ")"))
            {
                if (cause == OfflineCause.Unreachable) lock (gate) failure = SyncFailure.Network;
                Move(SyncState.Failed, "Не удалось получить игру с сервера: " + why + ".");
            }
            return;
        }

        if (remote.LauncherVersion > myVersion && exePath != null)
        {
            if (SelfUpdate(remote)) return;
            // This release wants a launcher this exe could not become, and
            // "ИГРАТЬ" does not ask for it again (Peek): it would fetch the
            // new launcher, fail the same way and hold the game each time.
            lock (gate) kept = Math.Max(kept, remote.Serial);
            // Not a reason to keep anyone out of a game that is installed and
            // whole: the old launcher plays it, and says where the new one is.
            if (PlayLocal(local, localM, OfflineCause.Launcher, "Вышла новая версия лаунчера, и поставить её самостоятельно не вышло. Скачайте её с сайта"))
                return;
            Move(SyncState.MustUpdate, "Вышла новая версия лаунчера, и поставить её самостоятельно не вышло. Скачайте её с сайта.");
            return;
        }

        Manifest m;
        byte[] mdata = null;
        if (local != null && localM != null && local.ManifestSha == remote.ManifestSha)
            m = localM;
        else
        {
            mdata = Fetch(root + remote.ManifestPath, remote.ManifestSize);
            try
            {
                if (mdata == null || mdata.LongLength != remote.ManifestSize || Hashes.Sha256Hex(mdata) != remote.ManifestSha)
                    throw new ReleaseException("список файлов релиза не сошёлся с указателем");
                m = Manifest.Read(mdata);
            }
            catch (ReleaseException e)
            {
                if (PlayLocal(local, localM, OfflineCause.Download, "Обновление не скачалось (" + e.Message + ")")) return;
                throw;
            }
        }

        // Windows without long-path support stops at 259 characters, and a
        // file in place also passes through "<name>.lava-new" and, if it is
        // kept aside, through .lava\replaced\<time>\, some 35 longer. A
        // folder too deep fails here, with a reason, not half-way through.
        int longest = 0;
        foreach (Entry e in m.Files) longest = Math.Max(longest, Full(e.Path).Length);
        if (longest + 40 > 259)
        {
            Move(SyncState.Failed, "Папка с лаунчером лежит слишком глубоко: пути к файлам игры выйдут за 260 знаков. " +
                 "Перенесите лаунчер в папку с коротким путём, например C:\\Games\\Lava, и запустите снова.");
            return;
        }

        List<Entry> need = Scan(m, true);
        if (need.Count > 0)
        {
            long bytes = Bytes(need), free = FreeSpace();
            lock (gate) { needBytes = bytes; freeBytes = free; }
            bool ask;
            lock (gate) ask = fresh && AskFirst && !confirmed;
            if (ask)
            {
                Move(SyncState.Setup, "Установить игру");
                return;
            }
            if (free < bytes + SPARE)
            {
                Move(SyncState.NoSpace, "Не хватает места на диске");
                return;
            }
            if (pausing)
            {
                Move(SyncState.Paused, "Загрузка приостановлена");
                return;
            }
            // Until the first file is put in place the installed release is
            // untouched, and a failed download leaves it playable.
            try { Download(need); }
            catch (PausedException)
            {
                Move(SyncState.Paused, "Загрузка приостановлена");
                return;
            }
            catch (Exception e)
            {
                if (localM != null && localM != m && PlayLocal(local, localM, OfflineCause.Download, "Обновление не скачалось (" + Short(e) + ")")) return;
                throw;
            }
            Apply(need);
            List<Entry> still = Scan(m, false);
            if (still.Count > 0)
                throw new ReleaseException("после обновления не сходится " + still[0].Path);
        }

        // Accepted: remembered only now that every file is in place.
        if (mdata != null) WriteState("manifest.txt", mdata);
        WriteState("current.txt", remoteDoc);
        WriteHighest(remote.Serial);
        SaveIndex();
        CleanStaging();
        lock (gate)
        {
            manifest = m;
            pointer = remote;
            source = m.Source;
            updated = need.Count;
            kept = Math.Max(kept, remote.Serial);
        }
        Move(SyncState.Ready, need.Count > 0
            ? "Игра обновлена: " + need.Count + " " + Files(need.Count)
            : "Игра в актуальном состоянии");
    }

    /// <summary>Play the release this folder last accepted, if it is still
    /// whole: Offline, with why in the note. False if there is none or it
    /// is not whole any more.</summary>
    bool PlayLocal(Pointer localP, Manifest localM, OfflineCause cause, string why)
    {
        if (localM == null) return false;
        if (Scan(localM, false).Count != 0) return false;
        lock (gate) { manifest = localM; pointer = localP; source = localM.Source; offline = cause; }
        SaveIndex();
        Move(SyncState.Offline, why + ". Играем на установленной версии.");
        return true;
    }

    // --- looking at the disk ------------------------------------------------------------

    /// <summary>The entries whose file is missing or not what the manifest says.</summary>
    List<Entry> Scan(Manifest m, bool report)
    {
        List<Entry> need = new List<Entry>();
        long toHash = 0;
        List<Entry> hash = new List<Entry>();
        foreach (Entry e in m.Files)
        {
            FileInfo fi = new FileInfo(Full(e.Path));
            if (!fi.Exists || fi.Length != e.Size) { need.Add(e); continue; }
            Index.Row r = index.Get(e.Path);
            if (!FullVerify && r != null && r.Size == fi.Length && r.Ticks == fi.LastWriteTimeUtc.Ticks)
            {
                if (r.Sha != e.Sha) need.Add(e);
                continue;
            }
            hash.Add(e);
            toHash += e.Size;
        }
        if (hash.Count > 0)
        {
            lock (gate) { doneBytes = 0; totalBytes = toHash; doneFiles = 0; totalFiles = hash.Count; }
            if (report) Move(SyncState.Scanning, "Проверяем файлы игры");
            // A few readers at once: one thread spends most of its time
            // waiting on the open of the next small file, not on the hash.
            int next = -1;
            List<Entry> bad = new List<Entry>();
            Thread[] readers = new Thread[Math.Max(1, Math.Min(4, Environment.ProcessorCount))];
            for (int i = 0; i < readers.Length; i++)
            {
                readers[i] = new Thread(delegate ()
                {
                    int at;
                    while ((at = Interlocked.Increment(ref next)) < hash.Count)
                    {
                        Entry e = hash[at];
                        string full = Full(e.Path);
                        string sha = null;
                        long size = 0;
                        try { sha = Hashes.FileSha(full, out size); }
                        catch (IOException) { }
                        catch (UnauthorizedAccessException) { }
                        if (sha != null)
                            index.Put(e.Path, size, new FileInfo(full).LastWriteTimeUtc.Ticks, sha, sha == e.Sha);
                        if (sha == null || sha != e.Sha) lock (bad) bad.Add(e);
                        lock (gate) { doneBytes += size; doneFiles++; }
                        if (report) Tick();
                    }
                });
                readers[i].IsBackground = true;
                readers[i].Start();
            }
            foreach (Thread t in readers) t.Join();
            need.AddRange(bad);
            SaveIndex();
        }
        return need;
    }

    string Full(string rel)
    {
        return Path.Combine(resDir, rel.Replace('/', Path.DirectorySeparatorChar));
    }

    // What a download of these entries costs: each blob once, however many
    // paths share it.
    static long Bytes(List<Entry> need)
    {
        Dictionary<string, long> blobs = new Dictionary<string, long>();
        foreach (Entry e in need) blobs[e.Sha] = e.Size;
        long n = 0;
        foreach (long v in blobs.Values) n += v;
        return n;
    }

    long FreeSpace()
    {
        try { return new DriveInfo(Path.GetPathRoot(gameDir)).AvailableFreeSpace; }
        catch { return long.MaxValue; }
    }

    // --- downloading ---------------------------------------------------------------------

    void Download(List<Entry> need)
    {
        // One download per blob, however many paths share it, and none for a
        // blob already sitting complete in staging from an interrupted run.
        Dictionary<string, Entry> blobs = new Dictionary<string, Entry>();
        foreach (Entry e in need) blobs[e.Sha] = e;
        Queue<Entry> queue = new Queue<Entry>();
        long total = 0;
        foreach (Entry e in blobs.Values)
        {
            if (StagedOk(e)) continue;
            queue.Enqueue(e);
            total += e.Size;
        }
        lock (gate) { doneBytes = 0; totalBytes = total; doneFiles = 0; totalFiles = queue.Count; }
        if (queue.Count == 0) return;
        Move(SyncState.Downloading, "Загружаем игру");

        ServicePointManager.DefaultConnectionLimit = Math.Max(ServicePointManager.DefaultConnectionLimit, WORKERS + 2);
        string failure = null;
        object qlock = new object();
        Thread[] workers = new Thread[Math.Min(WORKERS, queue.Count)];
        for (int i = 0; i < workers.Length; i++)
        {
            workers[i] = new Thread(delegate ()
            {
                while (true)
                {
                    Entry e;
                    lock (qlock)
                    {
                        if (failure != null || queue.Count == 0) return;
                        if (pausing) { failure = PAUSED; return; }
                        e = queue.Dequeue();
                    }
                    string err = FetchBlob(e);
                    if (err != null)
                    {
                        lock (qlock) { if (failure == null) failure = err; }
                        return;
                    }
                    lock (gate) doneFiles++;
                    Tick();
                }
            });
            workers[i].IsBackground = true;
            workers[i].Start();
        }
        foreach (Thread t in workers) t.Join();
        if (failure == PAUSED) throw new PausedException();
        if (failure != null) throw new ReleaseException(failure);
    }

    string Staged(string sha) { return Path.Combine(stagingDir, sha); }

    bool StagedOk(Entry e)
    {
        string p = Staged(e.Sha);
        try
        {
            if (!File.Exists(p) || new FileInfo(p).Length != e.Size) return false;
            long size;
            return Hashes.FileSha(p, out size) == e.Sha;
        }
        catch { return false; }
    }

    string BlobUrl(string sha) { return root + "store/" + sha.Substring(0, 2) + "/" + sha; }

    /// <summary>null when the blob is in staging, hashed; otherwise why not.</summary>
    string FetchBlob(Entry e)
    {
        string last = null;
        for (int attempt = 0; attempt < TRIES; attempt++)
        {
            if (attempt > 0) Thread.Sleep(1000 * attempt);
            last = FetchToFile(BlobUrl(e.Sha), Staged(e.Sha), e.Size, e.Sha, true);
            if (last == null || last == PAUSED) return last;
        }
        // The kind of the last try is the kind of the failure: a file that
        // keeps arriving with the wrong bytes, or the wrong number of them,
        // is not a dead line.
        bool wrong = last == HASH_MISMATCH || last == TOO_LONG || last == TOO_SHORT;
        lock (gate) failure = wrong ? SyncFailure.Corrupt : SyncFailure.Network;
        return "не удалось скачать " + e.Path + ": " + last;
    }

    /// <summary>Stream url into path, hashing on the way; the file appears
    /// under its name only if size and hash both match. null on success.</summary>
    string FetchToFile(string url, string path, long size, string sha, bool count)
    {
        string part = path + ".part";
        long got = 0;
        try
        {
            HttpWebRequest rq = Request(url);
            using (WebResponse rs = rq.GetResponse())
            using (Stream s = rs.GetResponseStream())
            using (System.Security.Cryptography.HashAlgorithm h = Hashes.New())
            using (FileStream fo = new FileStream(part, FileMode.Create, FileAccess.Write, FileShare.None, 1 << 16))
            {
                byte[] buf = new byte[1 << 16];
                int n;
                while ((n = s.Read(buf, 0, buf.Length)) > 0)
                {
                    got += n;
                    if (got > size) return TOO_LONG;
                    h.TransformBlock(buf, 0, n, null, 0);
                    fo.Write(buf, 0, n);
                    if (count) { lock (gate) doneBytes += n; Tick(); }
                    if (count && pausing)
                    {
                        lock (gate) doneBytes -= got;
                        return PAUSED;
                    }
                }
                h.TransformFinalBlock(buf, 0, 0);
                if (got != size) return TOO_SHORT;
                if (Hex.Encode(h.Hash) != sha) return HASH_MISMATCH;
            }
            if (File.Exists(path)) File.Delete(path);
            File.Move(part, path);
            return null;
        }
        catch (Exception x)
        {
            if (count) lock (gate) doneBytes -= got;
            return Short(x);
        }
        finally
        {
            try { if (File.Exists(part)) File.Delete(part); } catch { }
        }
    }

    // --- putting files in place ---------------------------------------------------------

    void Apply(List<Entry> need)
    {
        // A blob may stand under several paths: copied for all but its last.
        Dictionary<string, int> uses = new Dictionary<string, int>();
        foreach (Entry e in need) { int u; uses.TryGetValue(e.Sha, out u); uses[e.Sha] = u + 1; }
        string stamp = DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture);
        lock (gate) { doneFiles = 0; totalFiles = need.Count; }
        Move(SyncState.Downloading, "Устанавливаем файлы");
        foreach (Entry e in need)
        {
            string src = Staged(e.Sha);
            if (IsTexts(e) && !TextsCheck.Sane(File.ReadAllBytes(src)))
                throw new ReleaseException("таблица строк из релиза не прошла проверку");
            uses[e.Sha]--;
            Place(e, src, uses[e.Sha] > 0, stamp);
            lock (gate) doneFiles++;
            Tick();
        }
        SaveIndex();
    }

    // Case-blind like the file system and like LocalServer, which serves the
    // table under whatever case Flash asks for it.
    static bool IsTexts(Entry e)
    {
        return string.Equals(e.Path, "database/texts.xml", StringComparison.OrdinalIgnoreCase);
    }

    void Place(Entry e, string src, bool keepSource, string stamp)
    {
        string full = Full(e.Path);
        Directory.CreateDirectory(Path.GetDirectoryName(full));
        if (File.Exists(full))
        {
            // A file this launcher never vouched for may be the player's own
            // work: it is moved aside, never thrown away.
            FileInfo fi = new FileInfo(full);
            Index.Row r = index.Get(e.Path);
            bool ours = r != null && r.Release && r.Size == fi.Length && r.Ticks == fi.LastWriteTimeUtc.Ticks;
            if (!ours)
            {
                string aside = Path.Combine(stateDir, "replaced", stamp, e.Path.Replace('/', Path.DirectorySeparatorChar));
                Directory.CreateDirectory(Path.GetDirectoryName(aside));
                if (File.Exists(aside)) File.Delete(aside);
                File.Move(full, aside);
            }
        }
        string tmp = full + ".lava-new";
        if (File.Exists(tmp)) File.Delete(tmp);
        if (keepSource) File.Copy(src, tmp);
        else File.Move(src, tmp);
        if (File.Exists(full))
        {
            try { File.Replace(tmp, full, null); }
            catch (PlatformNotSupportedException) { File.Delete(full); File.Move(tmp, full); }
            catch (IOException) { File.Delete(full); File.Move(tmp, full); }
        }
        else File.Move(tmp, full);
        FileInfo done = new FileInfo(full);
        index.Put(e.Path, done.Length, done.LastWriteTimeUtc.Ticks, e.Sha, true);
    }

    // --- while the game runs ------------------------------------------------------------

    readonly object[] pathLocks = MakeLocks(64);

    static object[] MakeLocks(int n)
    {
        object[] a = new object[n];
        for (int i = 0; i < n; i++) a[i] = new object();
        return a;
    }

    /// <summary>The bytes of a release file, hashed as they are handed out;
    /// a file that no longer matches is fetched again first. null if the
    /// right bytes cannot be had -- the caller answers 404 rather than hand
    /// Flash anything else.</summary>
    public byte[] Serve(Entry e)
    {
        lock (pathLocks[(e.Path.ToLowerInvariant().GetHashCode() & 0x7fffffff) % pathLocks.Length])
        {
            string full = Full(e.Path);
            try
            {
                if (File.Exists(full))
                {
                    byte[] b = File.ReadAllBytes(full);
                    if (b.LongLength == e.Size && Hashes.Sha256Hex(b) == e.Sha) return b;
                }
            }
            catch { }
            // Changed since the check: mended from the store, the same way an
            // update puts a file in place.
            try
            {
                Directory.CreateDirectory(stagingDir);
                string err = FetchBlob(e);
                if (err != null) { Log.Miss("не удалось восстановить " + e.Path + ": " + err); return null; }
                if (IsTexts(e) && !TextsCheck.Sane(File.ReadAllBytes(Staged(e.Sha))))
                {
                    Log.Miss("таблица строк из хранилища не прошла проверку");
                    return null;
                }
                lock (index) Place(e, Staged(e.Sha), false, "repair-" + DateTime.Now.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture));
                SaveIndex();
                Log.Miss("восстановлен " + e.Path);
                byte[] b = File.ReadAllBytes(full);
                return Hashes.Sha256Hex(b) == e.Sha ? b : null;
            }
            catch (Exception x)
            {
                Log.Miss("не удалось восстановить " + e.Path + ": " + Short(x));
                return null;
            }
        }
    }

    // --- between runs ---------------------------------------------------------------------

    /// <summary>A look at the published pointer and at nothing else, for the
    /// window between runs. It is fetched as a run fetches it, past every
    /// cache, and checked as a run checks it, against the resource key; a
    /// pointer that does not verify is Unknown and never Newer, so a forged
    /// one cannot even start a run. Its serial is compared with one of two.
    /// Without again (the watch, and "ИГРАТЬ" after a run it started):
    /// the newest a run here has accepted or been offered, signed, so a
    /// release a run has already been through, taken or not, does not call
    /// the window back, and one that would not download is not fetched
    /// again every 15 s. With again (every other look of "ИГРАТЬ"): the newest
    /// this folder has accepted (.lava/serial), so a release a run was
    /// offered and failed to download is tried once more before the game
    /// starts on the one before it; except a release that wants a launcher
    /// this exe could not become, which would fetch the new launcher and
    /// fail the same way on every press. Nothing on the disk is read or
    /// written, so a look never gets in a run's way. It takes at most
    /// millis, whatever the network does: a name lookup is outside a
    /// request's own timeout, so the request runs on a thread of its own and
    /// is let go unanswered.</summary>
    public Peeked Peek(int millis, bool again, out long serial)
    {
        serial = 0;
        if (Running) return Peeked.Busy;
        long known;
        lock (gate) known = again ? kept : seen;
        if (known <= 0) return Peeked.Unknown;                 // no run has looked yet
        long found = 0;
        string url = root + "current.txt?t=" + DateTime.UtcNow.Ticks;
        Thread t = new Thread(delegate ()
        {
            try
            {
                Tls();
                byte[] doc = Fetch(url, 64 * 1024, millis);
                if (doc != null) found = Pointer.Read(resourceKeys, doc).Serial;
            }
            catch { /* not signed, not a pointer: nothing to go on */ }
        });
        t.IsBackground = true;
        t.Name = "lava-peek";
        t.Start();
        if (!t.Join(millis)) return Peeked.Unknown;
        if (found <= 0) return Peeked.Unknown;
        serial = found;
        if (Running) return Peeked.Busy;
        lock (gate) known = again ? kept : seen;               // a run may have ended meanwhile
        return Newer(found, known) ? Peeked.Newer : Peeked.Current;
    }

    /// <summary>Whether a published serial is newer than the one known
    /// (Peek). Nothing is newer than an unknown 0.</summary>
    public static bool Newer(long published, long known)
    {
        return known > 0 && published > known;
    }

    // --- a new launcher -------------------------------------------------------------------

    bool SelfUpdate(Pointer p)
    {
        Move(SyncState.Checking, "Обновляем лаунчер до версии " + p.LauncherVersion);
        try
        {
            byte[] doc = Fetch(root + "launcher/" + p.LauncherVersion + ".txt", 64 * 1024);
            if (doc == null) return false;
            Statement s = Statement.Read(launcherKeys, doc);
            if (s.Version != p.LauncherVersion || s.Sha != p.LauncherSha || s.Size != p.LauncherSize)
                return false;
            if (s.Version <= myVersion) return false;
            string fresh = exePath + ".new", old = exePath + ".old";
            string err = FetchToFile(root + p.LauncherPath, fresh, s.Size, s.Sha, false);
            if (err != null) return false;
            // A running exe cannot be overwritten, but it can be renamed:
            // the old one steps aside, the new one takes its name. An
            // antivirus that has just scanned the new file holds it for a
            // moment, hence the retries.
            try { if (File.Exists(old)) File.Delete(old); }
            catch { old = exePath + "." + DateTime.UtcNow.Ticks + ".old"; }
            Retry(delegate { File.Move(exePath, old); });
            try { Retry(delegate { File.Move(fresh, exePath); }); }
            catch
            {
                Retry(delegate { File.Move(old, exePath); });
                throw;
            }
            NewVersion = s.Version;
            Move(SyncState.Restarting, "Лаунчер обновлён до версии " + s.Version + ", перезапускаем");
            return true;
        }
        catch (Exception e)
        {
            lock (gate) note = Short(e);
            return false;
        }
    }

    static void Retry(ThreadStart act)
    {
        for (int i = 0; ; i++)
        {
            try { act(); return; }
            catch (IOException) { if (i >= 5) throw; }
            catch (UnauthorizedAccessException) { if (i >= 5) throw; }
            Thread.Sleep(300);
        }
    }

    /// <summary>What a previous self-update left behind, once its process
    /// is gone. Only the old exe: a stale .new is overwritten by the next
    /// download anyway, and deleting it here could race one in progress.</summary>
    public static void CleanOld(string exePath)
    {
        string dir = Path.GetDirectoryName(exePath);
        string name = Path.GetFileName(exePath);
        for (int i = 0; i < 25; i++)
        {
            bool left = false;
            try
            {
                foreach (string f in Directory.GetFiles(dir, name + "*.old"))
                {
                    try { File.Delete(f); } catch { left = true; }
                }
            }
            catch { return; }
            if (!left) return;
            Thread.Sleep(200);
        }
    }

    // --- the folder's memory -------------------------------------------------------------

    byte[] ReadState(string name)
    {
        try { return File.ReadAllBytes(Path.Combine(stateDir, name)); }
        catch { return null; }
    }

    void WriteState(string name, byte[] data)
    {
        string path = Path.Combine(stateDir, name);
        string tmp = path + ".tmp";
        File.WriteAllBytes(tmp, data);
        if (File.Exists(path)) File.Replace(tmp, path, null);
        else File.Move(tmp, path);
    }

    long ReadHighest()
    {
        byte[] b = ReadState("serial");
        long v;
        return b != null && long.TryParse(Encoding.ASCII.GetString(b).Trim(), NumberStyles.None,
                                          CultureInfo.InvariantCulture, out v) ? v : 0;
    }

    void WriteHighest(long serial)
    {
        if (serial > ReadHighest())
            WriteState("serial", Encoding.ASCII.GetBytes(serial.ToString(CultureInfo.InvariantCulture) + "\n"));
    }

    void SaveIndex()
    {
        try { lock (index) index.Save(Path.Combine(stateDir, "index.tsv")); }
        catch { /* a lost index costs one full check next time */ }
    }

    void CleanStaging()
    {
        try
        {
            foreach (string f in Directory.GetFiles(stagingDir)) try { File.Delete(f); } catch { }
        }
        catch { }
        // Files kept aside: the five newest batches, which is enough to get
        // back what a player had and not enough to fill a disk over a year.
        try
        {
            string aside = Path.Combine(stateDir, "replaced");
            if (!Directory.Exists(aside)) return;
            string[] dirs = Directory.GetDirectories(aside);
            Array.Sort(dirs, StringComparer.Ordinal);
            for (int i = 0; i < dirs.Length - 5; i++)
                try { Directory.Delete(dirs[i], true); } catch { }
        }
        catch { }
    }

    // --- network ----------------------------------------------------------------------------

    // .NET 4 starts with SSL3 and TLS 1.0 only, and the site speaks neither
    // (the reason the old Updater measured it): every https request would fail.
    static void Tls()
    {
        try
        {
            ServicePointManager.SecurityProtocol =
                SecurityProtocolType.Tls12 | SecurityProtocolType.Tls11 | SecurityProtocolType.Tls;
        }
        catch { }
    }

    HttpWebRequest Request(string url, int timeout = TIMEOUT_MS)
    {
        HttpWebRequest rq = (HttpWebRequest)WebRequest.Create(url);
        rq.Timeout = timeout;
        rq.ReadWriteTimeout = timeout;
        rq.UserAgent = "LavaReborn/" + myVersion;
        rq.CachePolicy = new HttpRequestCachePolicy(HttpRequestCacheLevel.NoCacheNoStore);
        rq.AutomaticDecompression = DecompressionMethods.None;
        return rq;
    }

    byte[] Fetch(string url, long max, int timeout = TIMEOUT_MS)
    {
        try
        {
            HttpWebRequest rq = Request(url, timeout);
            using (WebResponse rs = rq.GetResponse())
            using (Stream s = rs.GetResponseStream())
            using (MemoryStream m = new MemoryStream())
            {
                byte[] buf = new byte[1 << 16];
                int n;
                while ((n = s.Read(buf, 0, buf.Length)) > 0)
                {
                    if (m.Length + n > max) return null;
                    m.Write(buf, 0, n);
                }
                return m.ToArray();
            }
        }
        catch { return null; }
    }

    static string Files(int n)
    {
        int d = n % 100;
        if (d >= 11 && d <= 14) return "файлов";
        switch (n % 10)
        {
            case 1: return "файл";
            case 2: case 3: case 4: return "файла";
            default: return "файлов";
        }
    }

    public static string Short(Exception e)
    {
        string m = e.Message;
        if (m == null) return e.GetType().Name;
        m = m.Replace("\r", " ").Replace("\n", " ").Trim();
        return m.Length > 160 ? m.Substring(0, 160) + "…" : m;
    }
}

// A download stopped by Sync.Pause(): not a failure, a state.
class PausedException : Exception { }

// When the window looks at the published pointer on its own (Sync.Peek):
// every EVERY_MS for SPAN_MS once armed, and not at all once stopped. A
// deploy closes the game when it restarts the server, waits up to 240 s
// for the server and 20 s more, and only then publishes the release that
// goes with it (deploy/remote/lava-gate.sh, 7b and 9b), so the check made
// as the game closed sees the old one; five minutes of looks catch the new
// one. Times are Environment.TickCount, and differences of it, so the
// wrap after 24.9 days of uptime changes nothing. No clock and no timer in
// here: the window ticks it, launcher/test walks it.
class Watch
{
    public const int EVERY_MS = 15000;
    public const int SPAN_MS = 5 * 60 * 1000;

    bool on;
    int armed, last;

    public bool On { get { return on; } }

    public void Arm(int now)
    {
        on = true;
        armed = now;
        last = now;
    }

    public void Stop() { on = false; }

    /// <summary>Whether to look now. Past the span the watch stops itself
    /// and says no from then on.</summary>
    public bool Due(int now)
    {
        if (!on) return false;
        if (unchecked(now - armed) > SPAN_MS) { on = false; return false; }
        if (unchecked(now - last) < EVERY_MS) return false;
        last = now;
        return true;
    }

    /// <summary>What a look that found a newer release leads to. While the
    /// game runs, only Tell: a run would change files the game is reading,
    /// and a new launcher restarts this one, taking the game's web server
    /// with it. With the game on its way or the folder being changed,
    /// nothing. Otherwise Take, from a folder that is playable as it
    /// stands; a paused download, a question before an install or a
    /// failure are the player's to resume.</summary>
    public static Act Decide(bool inGame, bool busy, SyncState state)
    {
        if (inGame) return Act.Tell;
        if (busy) return Act.Nothing;
        return state == SyncState.Ready || state == SyncState.Offline ? Act.Take : Act.Nothing;
    }

    public enum Act
    {
        Nothing,
        Take,          // a run now, as after a game
        Tell,          // a word in the tray, nothing installed
    }
}

// What the launcher has hashed: path, size, modification time and sha256,
// and whether that sha256 was a release's. A file whose size and time are
// unchanged is not read again at the next start.
class Index
{
    public class Row
    {
        public long Size, Ticks;
        public string Sha;
        public bool Release;
    }

    readonly Dictionary<string, Row> rows = new Dictionary<string, Row>(StringComparer.OrdinalIgnoreCase);

    public Row Get(string path)
    {
        lock (rows)
        {
            Row r;
            return rows.TryGetValue(path, out r) ? r : null;
        }
    }

    public void Put(string path, long size, long ticks, string sha, bool release)
    {
        Row r = new Row();
        r.Size = size; r.Ticks = ticks; r.Sha = sha; r.Release = release;
        lock (rows) rows[path] = r;
    }

    public static Index Load(string file)
    {
        Index ix = new Index();
        try
        {
            foreach (string line in File.ReadAllLines(file, Encoding.UTF8))
            {
                string[] p = line.Split('\t');
                if (p.Length != 5 || p[3].Length != 64) continue;
                Row r = new Row();
                if (!long.TryParse(p[1], NumberStyles.None, CultureInfo.InvariantCulture, out r.Size)) continue;
                if (!long.TryParse(p[2], NumberStyles.None, CultureInfo.InvariantCulture, out r.Ticks)) continue;
                r.Sha = p[3];
                r.Release = p[4] == "r";
                ix.rows[p[0]] = r;
            }
        }
        catch { }
        return ix;
    }

    public void Save(string file)
    {
        StringBuilder sb = new StringBuilder();
        lock (rows)
        {
            foreach (KeyValuePair<string, Row> kv in rows)
                sb.Append(kv.Key).Append('\t')
                  .Append(kv.Value.Size.ToString(CultureInfo.InvariantCulture)).Append('\t')
                  .Append(kv.Value.Ticks.ToString(CultureInfo.InvariantCulture)).Append('\t')
                  .Append(kv.Value.Sha).Append('\t')
                  .Append(kv.Value.Release ? "r" : "-").Append('\n');
        }
        string tmp = file + ".tmp";
        File.WriteAllText(tmp, sb.ToString(), new UTF8Encoding(false));
        if (File.Exists(file)) File.Replace(tmp, file, null);
        else File.Move(tmp, file);
    }
}
