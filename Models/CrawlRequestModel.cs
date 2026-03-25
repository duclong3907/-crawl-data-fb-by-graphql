namespace GroupPostsCrawler.Models;

public class CrawlRequestModel
{
    public string GroupId { get; set; } = string.Empty;
    public string GroupUrl { get; set; } = string.Empty;
    public string DateFrom { get; set; } = string.Empty;
    public string DateTo { get; set; } = string.Empty;
    public int MaxPosts { get; set; } = 100;
    public bool ClearCookies { get; set; } = false;
}
