using System.Diagnostics;
using System.Text.Json;
using Microsoft.AspNetCore.Mvc;
using GroupPostsCrawler.Models;
using GroupPostsCrawler.Services;

namespace GroupPostsCrawler.Controllers;

public class HomeController : Controller
{
    private readonly PythonCrawlerService _crawlerService;

    public HomeController(PythonCrawlerService crawlerService)
    {
        _crawlerService = crawlerService;
    }

    public IActionResult Index()
    {
        return View();
    }

    /// <summary>
    /// Start a crawl session and return session ID.
    /// </summary>
    [HttpPost]
    public IActionResult StartCrawl([FromBody] CrawlRequestModel request)
    {
        if (string.IsNullOrWhiteSpace(request.GroupUrl)
            && string.IsNullOrWhiteSpace(request.GroupId))
        {
            return BadRequest(new
            {
                success = false,
                error = "Vui lòng nhập Group URL hoặc Group ID"
            });
        }

        var sessionId = _crawlerService.StartCrawl(request);
        return Json(new { sessionId });
    }

    /// <summary>
    /// SSE endpoint for real-time crawl progress.
    /// </summary>
    [HttpGet]
    public async Task CrawlProgress([FromQuery] string sessionId)
    {
        Response.ContentType = "text/event-stream";
        Response.Headers.CacheControl = "no-cache";
        Response.Headers.Connection = "keep-alive";

        var session = _crawlerService.GetSession(sessionId);
        if (session == null)
        {
            await WriteSseEvent("error",
                JsonSerializer.Serialize(new { error = "Session not found" }));
            return;
        }

        var ct = HttpContext.RequestAborted;

        while (!ct.IsCancellationRequested)
        {
            var progress = await session.WaitForProgressAsync(ct, 1000);

            // Heartbeat with elapsed time
            var elapsed = (DateTime.UtcNow - session.StartedAt).TotalSeconds;
            await WriteSseEvent("heartbeat",
                JsonSerializer.Serialize(new { elapsed = Math.Round(elapsed) }));

            if (progress != null)
            {
                await WriteSseEvent("progress",
                    JsonSerializer.Serialize(progress));
            }

            if (session.IsComplete)
            {
                // Drain remaining progress
                while (true)
                {
                    var remaining = await session.WaitForProgressAsync(ct, 100);
                    if (remaining == null) break;
                    await WriteSseEvent("progress",
                        JsonSerializer.Serialize(remaining));
                }

                // Send final result
                var result = session.Result ?? new CrawlResultModel
                {
                    Success = false,
                    Error = "Unknown error"
                };
                await WriteSseEvent("result",
                    JsonSerializer.Serialize(result));

                _crawlerService.RemoveSession(sessionId);
                break;
            }
        }
    }

    private async Task WriteSseEvent(string eventType, string data)
    {
        var message = $"event: {eventType}\ndata: {data}\n\n";
        await Response.WriteAsync(message);
        await Response.Body.FlushAsync();
    }

    [ResponseCache(
        Duration = 0,
        Location = ResponseCacheLocation.None,
        NoStore = true)]
    public IActionResult Error()
    {
        return View(new ErrorViewModel
        {
            RequestId = Activity.Current?.Id
                        ?? HttpContext.TraceIdentifier
        });
    }
}
