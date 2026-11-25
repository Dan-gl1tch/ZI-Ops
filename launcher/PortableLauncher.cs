using System;
using System.Diagnostics;
using System.IO;
using System.IO.Compression;
using System.Reflection;
using System.Security.Cryptography;
using System.Text;
using System.Threading;
using System.Windows.Forms;

internal static class PortableLauncher
{
    [STAThread]
    private static int Main(string[] args)
    {
        try
        {
            string selfDirectory = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
            string local = Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData);
            // Respect an explicit data directory for isolated checks and managed environments.
            string explicitLocal = Environment.GetEnvironmentVariable("LOCALAPPDATA");
            if (!String.IsNullOrWhiteSpace(explicitLocal)) local = explicitLocal;
            string cacheRoot = Path.Combine(local, "ZI-Ops", "portable");
            Directory.CreateDirectory(cacheRoot);
            string destination = Path.Combine(cacheRoot, PayloadInfo.Hash);
            using (var mutex = new Mutex(false, @"Local\ZI-Ops-Portable-" + PayloadInfo.Hash))
            {
                bool acquired = false;
                try
                {
                    try { acquired = mutex.WaitOne(TimeSpan.FromMinutes(10)); }
                    catch (AbandonedMutexException) { acquired = true; }
                    if (!acquired) throw new IOException("Timed out waiting for another copy to finish extracting.");
                    if (!Ready(destination)) Extract(destination, cacheRoot);
                }
                finally { if (acquired) mutex.ReleaseMutex(); }
            }
            if (args.Length == 1 && args[0] == "--portable-check") return 0;
            var start = new ProcessStartInfo(Path.Combine(destination, "ZI-Ops.exe"));
            start.WorkingDirectory = selfDirectory;
            start.UseShellExecute = false;
            start.Arguments = JoinArguments(args);
            using (Process child = Process.Start(start))
            {
                child.WaitForExit();
                return child.ExitCode;
            }
        }
        catch (Exception error)
        {
            MessageBox.Show("Не удалось запустить ZI-Ops.\n\n" + error.Message,
                "ZI-Ops", MessageBoxButtons.OK, MessageBoxIcon.Error);
            return 1;
        }
    }

    private static bool Ready(string directory)
    {
        return File.Exists(Path.Combine(directory, ".ready")) &&
            File.Exists(Path.Combine(directory, "ZI-Ops.exe")) &&
            File.Exists(Path.Combine(directory, "runtime", "bin", "server", "jvm.dll"));
    }

    private static void Extract(string destination, string cacheRoot)
    {
        string staging = Path.Combine(cacheRoot, "extract-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(staging);
        try
        {
            using (Stream payload = Assembly.GetExecutingAssembly().GetManifestResourceStream("Payload.zip"))
            {
                if (payload == null) throw new InvalidDataException("Embedded application is missing.");
                using (var hash = SHA256.Create())
                {
                    string actual = BitConverter.ToString(hash.ComputeHash(payload)).Replace("-", "").ToLowerInvariant();
                    if (actual != PayloadInfo.Hash) throw new InvalidDataException("Embedded application is damaged.");
                }
                payload.Position = 0;
                string root = Path.GetFullPath(staging) + Path.DirectorySeparatorChar;
                using (var archive = new ZipArchive(payload, ZipArchiveMode.Read))
                {
                    foreach (var entry in archive.Entries)
                    {
                        string target = Path.GetFullPath(Path.Combine(staging, entry.FullName));
                        if (!target.StartsWith(root, StringComparison.OrdinalIgnoreCase))
                            throw new InvalidDataException("Invalid archive path.");
                        if (String.IsNullOrEmpty(entry.Name)) Directory.CreateDirectory(target);
                        else
                        {
                            Directory.CreateDirectory(Path.GetDirectoryName(target));
                            using (Stream input = entry.Open())
                            using (Stream output = File.Create(target)) input.CopyTo(output);
                        }
                    }
                }
            }
            File.WriteAllText(Path.Combine(staging, ".ready"), PayloadInfo.Hash);
            if (!Ready(staging)) throw new InvalidDataException("Extracted application is incomplete.");
            // Only an incomplete cache of this exact payload can be replaced here.
            if (Directory.Exists(destination)) Directory.Delete(destination, true);
            Directory.Move(staging, destination);
        }
        finally { if (Directory.Exists(staging)) Directory.Delete(staging, true); }
    }

    private static string JoinArguments(string[] args)
    {
        var result = new StringBuilder();
        foreach (string arg in args)
        {
            if (result.Length > 0) result.Append(' ');
            result.Append('"');
            int slashes = 0;
            foreach (char c in arg)
            {
                if (c == '\\') { slashes++; continue; }
                if (c == '"') { result.Append('\\', slashes * 2 + 1); result.Append(c); }
                else { result.Append('\\', slashes); result.Append(c); }
                slashes = 0;
            }
            result.Append('\\', slashes * 2); result.Append('"');
        }
        return result.ToString();
    }
}
