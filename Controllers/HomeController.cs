using System.Diagnostics;
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

    [HttpPost]
    public async Task<IActionResult> Crawl([FromBody] CrawlRequestModel request)
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

        var result = await _crawlerService.CrawlGroupPostsAsync(request);
        return Json(result);
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
