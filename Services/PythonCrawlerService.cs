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

    public async Task<CrawlResultModel> CrawlGroupPostsAsync(CrawlRequestModel request)
    {
        try
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

            return await RunPythonProcess<CrawlResultModel>(
                args.ToString(), timeoutMs: 600_000
            );
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error running Python crawler");
            return new CrawlResultModel
            {
                Success = false,
                Error = $"Internal error: {ex.Message}"
            };
        }
    }

    private async Task<T> RunPythonProcess<T>(
        string arguments, int timeoutMs = 600_000) where T : new()
    {
        var processInfo = new ProcessStartInfo
        {
            FileName = _pythonPath,
            Arguments = arguments,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            UseShellExecute = false,
            CreateNoWindow = false,
            StandardOutputEncoding = Encoding.UTF8,
            StandardErrorEncoding = Encoding.UTF8
        };

        using var process = new Process { StartInfo = processInfo };

        var stdoutBuilder = new StringBuilder();
        var stderrBuilder = new StringBuilder();

        process.OutputDataReceived += (_, e) =>
        {
            if (e.Data != null) stdoutBuilder.AppendLine(e.Data);
        };

        process.ErrorDataReceived += (_, e) =>
        {
            if (e.Data != null)
            {
                _logger.LogInformation("[Python] {Line}", e.Data);
                stderrBuilder.AppendLine(e.Data);
            }
        };

        process.Start();
        process.BeginOutputReadLine();
        process.BeginErrorReadLine();

        var completed = await Task.Run(
            () => process.WaitForExit(timeoutMs)
        );

        if (!completed)
        {
            process.Kill();
            throw new TimeoutException(
                $"Crawling timed out after {timeoutMs / 60000} minutes"
            );
        }

        var stdout = stdoutBuilder.ToString().Trim();
        _logger.LogInformation(
            "Python exited with code: {Code}", process.ExitCode
        );

        if (string.IsNullOrEmpty(stdout))
        {
            throw new InvalidOperationException(
                $"No output from Python. Stderr: {stderrBuilder}"
            );
        }

        return JsonSerializer.Deserialize<T>(stdout)
               ?? throw new InvalidOperationException(
                   "Failed to parse Python output"
               );
    }
}
