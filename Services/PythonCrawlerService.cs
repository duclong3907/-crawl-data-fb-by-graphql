using System.Collections.Concurrent;
using System.Diagnostics;
using System.Text;
using System.Text.Json;
using GroupPostsCrawler.Models;

namespace GroupPostsCrawler.Services;

public class PythonCrawlerService
{
    private readonly ILogger<PythonCrawlerService> _logger;
    private readonly string _scriptPath;
    private readonly string _pythonPath;

    // Active crawl sessions for SSE progress streaming
    private readonly ConcurrentDictionary<string, CrawlSession> _sessions = new();

    public PythonCrawlerService(
        ILogger<PythonCrawlerService> logger,
        IConfiguration configuration)
    {
        _logger = logger;
        _scriptPath = Path.Combine(
            AppDomain.CurrentDomain.BaseDirectory,
            "..", "..", "..", "Scripts", "crawl_group_posts.py"
        );
        _scriptPath = Path.GetFullPath(_scriptPath);
        _pythonPath = configuration.GetValue<string>("PythonPath") ?? "python";
    }

    /// <summary>
    /// Start a crawl and return session ID for progress tracking.
    /// </summary>
    public string StartCrawl(CrawlRequestModel request)
    {
        var sessionId = Guid.NewGuid().ToString("N")[..12];
        var session = new CrawlSession();
        _sessions[sessionId] = session;

        _ = Task.Run(async () =>
        {
            try
            {
                var result = await RunCrawlProcess(request, session);
                session.Result = result;
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Crawl session {Id} error", sessionId);
                session.Result = new CrawlResultModel
                {
                    Success = false,
                    Error = $"Internal error: {ex.Message}"
                };
            }
            finally
            {
                session.IsComplete = true;
            }
        });

        return sessionId;
    }

    public CrawlSession? GetSession(string sessionId)
    {
        _sessions.TryGetValue(sessionId, out var session);
        return session;
    }

    public void RemoveSession(string sessionId)
    {
        _sessions.TryRemove(sessionId, out _);
    }

    private async Task<CrawlResultModel> RunCrawlProcess(
        CrawlRequestModel request, CrawlSession session)
    {
        if (!File.Exists(_scriptPath))
        {
            return new CrawlResultModel
            {
                Success = false,
                Error = $"Python script not found at: {_scriptPath}"
            };
        }

        // Build arguments
        var args = new StringBuilder();
        args.Append($"\"{_scriptPath}\"");

        if (!string.IsNullOrWhiteSpace(request.GroupUrl))
            args.Append($" --group-url \"{request.GroupUrl}\"");
        else if (!string.IsNullOrWhiteSpace(request.GroupId))
            args.Append($" --group-id \"{request.GroupId}\"");

        args.Append($" --max {request.MaxPosts}");

        if (!string.IsNullOrWhiteSpace(request.DateFrom))
            args.Append($" --date-from \"{request.DateFrom}\"");

        if (!string.IsNullOrWhiteSpace(request.DateTo))
            args.Append($" --date-to \"{request.DateTo}\"");

        if (request.ClearCookies)
            args.Append(" --clear-cookies");

        _logger.LogInformation(
            "Starting group posts crawler: {Args}",
            args.ToString()[..Math.Min(args.Length, 100)]
        );

        var processInfo = new ProcessStartInfo
        {
            FileName = _pythonPath,
            Arguments = args.ToString(),
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = false,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };

        using var process = new Process { StartInfo = processInfo };

        var stdoutBuilder = new StringBuilder();

        process.OutputDataReceived += (_, e) =>
        {
            if (e.Data != null) stdoutBuilder.AppendLine(e.Data);
        };

        process.ErrorDataReceived += (_, e) =>
        {
            if (e.Data == null) return;

            // Parse structured progress messages
            if (e.Data.StartsWith("PROGRESS:"))
            {
                var json = e.Data["PROGRESS:".Length..];
                try
                {
                    var opts = new JsonSerializerOptions
                    {
                        PropertyNameCaseInsensitive = true
                    };
                    var progress = JsonSerializer
                        .Deserialize<ProgressData>(json, opts);
                    if (progress != null)
                    {
                        session.EnqueueProgress(progress);
                    }
                }
                catch (JsonException)
                {
                    _logger.LogWarning(
                        "Failed to parse progress: {Data}", json);
                }
            }
            else
            {
                _logger.LogInformation("[Python] {Line}", e.Data);
            }
        };

        process.Start();
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();

        // Dynamic timeout: ~15s per post + 5 min base (login/capture)
        // Minimum 30 minutes, max 4 hours
        var timeoutMs = Math.Clamp(
            (request.MaxPosts * 15_000) + 300_000,
            1_800_000,   // 30 min minimum
            14_400_000   // 4 hours max
        );
        var timeoutMinutes = timeoutMs / 60_000;

        var completed = await Task.Run(
            () => process.WaitForExit(timeoutMs)
        );

        if (!completed)
        {
            process.Kill();
            throw new TimeoutException(
                $"Crawling timed out after {timeoutMinutes} minutes"
            );
        }

        var stdout = stdoutBuilder.ToString().Trim();
        _logger.LogInformation(
            "Python exited with code: {Code}", process.ExitCode
        );

        if (string.IsNullOrEmpty(stdout))
        {
            throw new InvalidOperationException(
                "No output from Python."
            );
        }

        return JsonSerializer.Deserialize<CrawlResultModel>(stdout)
               ?? throw new InvalidOperationException(
                   "Failed to parse Python output"
               );
    }
}

/// <summary>
/// Tracks an active crawl session with progress queue.
/// </summary>
public class CrawlSession
{
    private readonly ConcurrentQueue<ProgressData> _progressQueue = new();
    private readonly SemaphoreSlim _signal = new(0);

    public bool IsComplete { get; set; }
    public CrawlResultModel? Result { get; set; }
    public DateTime StartedAt { get; } = DateTime.UtcNow;

    public void EnqueueProgress(ProgressData data)
    {
        _progressQueue.Enqueue(data);
        _signal.Release();
    }

    public async Task<ProgressData?> WaitForProgressAsync(
        CancellationToken ct, int timeoutMs = 3000)
    {
        try
        {
            var acquired = await _signal.WaitAsync(timeoutMs, ct);
            if (acquired && _progressQueue.TryDequeue(out var data))
                return data;
        }
        catch (OperationCanceledException) { }
        return null;
    }
}

/// <summary>
/// Structured progress data from Python crawler.
/// </summary>
public class ProgressData
{
    [System.Text.Json.Serialization.JsonPropertyName("phase")]
    public string Phase { get; set; } = "";

    [System.Text.Json.Serialization.JsonPropertyName("message")]
    public string Message { get; set; } = "";

    [System.Text.Json.Serialization.JsonPropertyName("current")]
    public int Current { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("total")]
    public int Total { get; set; }

    [System.Text.Json.Serialization.JsonPropertyName("page")]
    public int Page { get; set; }
}
