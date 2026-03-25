using System.Text.Json.Serialization;

namespace GroupPostsCrawler.Models;

public class CrawlResultModel
{
    [JsonPropertyName("success")]
    public bool Success { get; set; }

    [JsonPropertyName("error")]
    public string? Error { get; set; }

    [JsonPropertyName("total")]
    public int Total { get; set; }

    [JsonPropertyName("group_id")]
    public string GroupId { get; set; } = string.Empty;

    [JsonPropertyName("group_name")]
    public string GroupName { get; set; } = string.Empty;

    [JsonPropertyName("posts")]
    public List<PostModel> Posts { get; set; } = [];

    [JsonPropertyName("has_more")]
    public bool HasMore { get; set; }

    [JsonPropertyName("next_cursor")]
    public string? NextCursor { get; set; }
}

public class PostModel
{
    [JsonPropertyName("post_id")]
    public string PostId { get; set; } = string.Empty;

    [JsonPropertyName("author_name")]
    public string AuthorName { get; set; } = string.Empty;

    [JsonPropertyName("author_id")]
    public string AuthorId { get; set; } = string.Empty;

    [JsonPropertyName("content")]
    public string Content { get; set; } = string.Empty;

    [JsonPropertyName("created_time")]
    public long CreatedTime { get; set; }

    [JsonPropertyName("created_time_formatted")]
    public string CreatedTimeFormatted { get; set; } = string.Empty;

    [JsonPropertyName("reaction_count")]
    public int ReactionCount { get; set; }

    [JsonPropertyName("comment_count")]
    public int CommentCount { get; set; }

    [JsonPropertyName("share_count")]
    public int ShareCount { get; set; }

    [JsonPropertyName("media_urls")]
    public List<string> MediaUrls { get; set; } = [];

    [JsonPropertyName("post_url")]
    public string PostUrl { get; set; } = string.Empty;

    [JsonPropertyName("post_type")]
    public string PostType { get; set; } = string.Empty;
}
