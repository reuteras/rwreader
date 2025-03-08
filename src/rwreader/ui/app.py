"""Main application class for rwreader."""

import logging
import sys
import webbrowser
from typing import Any, ClassVar, Dict, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, ListItem, ListView, Static

from ..client import ReadwiseClient
from ..config import Configuration
from .widgets.article_viewer import ArticleViewer
from .screens.help import HelpScreen

logger: logging.Logger = logging.getLogger(name=__name__)


class RWReader(App[None]):
    """A Textual app for Readwise Reader."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        # Navigation
        ("j", "next_item", "Next item"),
        ("k", "previous_item", "Previous item"),
        ("tab", "focus_next_pane", "Next pane"),
        ("shift+tab", "focus_previous_pane", "Previous pane"),
        
        # Article actions
        ("r", "toggle_read", "Toggle read/unread"),
        ("a", "toggle_archive", "Toggle archive"),
        ("l", "move_to_later", "Move to Later"),
        ("i", "move_to_inbox", "Move to Inbox"),
        ("o", "open_in_browser", "Open in browser"),
        ("m", "show_metadata", "Show metadata"),
        
        # App controls
        ("?", "toggle_help", "Help"),
        ("h", "toggle_help", "Help"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("c", "clear", "Clear"),
        ("G", "refresh", "Refresh"),
        ("comma", "refresh", "Refresh"),
        ("q", "quit", "Quit"),

        # Debug bindings - hidden from help menu
        ("ctrl+d", "debug_categories", "None"),  # Debug categories
        ("ctrl+a", "debug_article", "None"),     # Debug current article
        ("ctrl+r", "debug_reset_cache", "None"), # Reset cache
        ("ctrl+D", "debug_api", "None"),         # Debug API calls
    ]
    CSS_PATH = ["styles.tcss"]

    def __init__(self) -> None:
        """Initialize the app and connect to Readwise API."""
        super().__init__()  # Initialize first for early access to notify/etc.

        try:
            # Load the configuration
            self.configuration = Configuration(arguments=sys.argv[1:])

            # Set theme based on configuration
            self.theme = (
                "textual-dark"
                if self.configuration.default_theme == "dark"
                else "textual-light"
            )

            # Connect to Readwise API
            self.client = ReadwiseClient(
                token=self.configuration.token,
                cache_size=self.configuration.cache_size,
            )
            
            # State variables
            self.current_article_id: Optional[str] = None
            self.current_article: Optional[Dict[str, Any]] = None
            self.current_collection_id: Optional[str] = None
            self.current_view: str = "library"  # "library" or "collection"
            self.content_markdown: str = "# Welcome to Readwise Reader TUI\n\nSelect an article to read."
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            print(f"Error: {e}")
            sys.exit(1)

    def compose(self) -> ComposeResult:
        """Compose the three-pane layout."""
        yield Header(show_clock=True)
        with Horizontal():
            yield ListView(id="collections")
            with Vertical():
                yield ListView(id="articles")
                yield ArticleViewer(markdown=self.content_markdown, id="content")
        yield Footer()

    async def on_mount(self) -> None:
        """Load library data when the app is mounted."""
        await self.refresh_collections()
        await self.refresh_articles()

    async def refresh_collections(self) -> None:
        """Load collections from Readwise."""
        try:
            # Get the collections list view
            list_view: ListView = self.query_one("#collections", ListView)
            await list_view.clear()
            
            # Add library sections
            list_view.append(ListItem(Static("LIBRARY"), id="lib_header"))
            list_view.append(ListItem(Static("Inbox"), id="lib_inbox"))
            list_view.append(ListItem(Static("Later"), id="lib_later"))
            list_view.append(ListItem(Static("Archive"), id="lib_archive"))
            
            # Add collections
            collections = self.client.get_collections()
            if collections:
                list_view.append(ListItem(Static("COLLECTIONS"), id="col_header"))
                
                # Keep track of used IDs to avoid duplicates
                used_ids = set()
                
                for index, collection in enumerate(collections):
                    collection_id = collection.get("id")
                    collection_name = collection.get("name", "Unnamed Collection")
                    
                    # Create a unique ID if none exists or is duplicate
                    if not collection_id or f"col_{collection_id}" in used_ids:
                        collection_id = f"custom_{index}"
                        
                    item_id = f"col_{collection_id}"
                    used_ids.add(item_id)
                    
                    list_view.append(ListItem(Static(collection_name), id=item_id))
        except Exception as e:
            logger.error(f"Error refreshing collections: {e}")
            self.notify(message=f"Error refreshing collections: {e}", title="Error", severity="error")

    async def refresh_articles(self) -> None:
        """Load articles based on current view."""
        try:
            # Get the articles list view
            list_view: ListView = self.query_one("#articles", ListView)
            await list_view.clear()
            
            # Display the current view in the header of the articles panel
            header_text = "Articles"
            if self.current_view == "inbox":
                header_text = "Inbox"
            elif self.current_view == "later":
                header_text = "Later"
            elif self.current_view == "archive":
                header_text = "Archive"
            elif self.current_view == "collection" and self.current_collection_id:
                # Try to find collection name
                for collection in self.client.get_collections():
                    if str(collection.get("id")) == str(self.current_collection_id):
                        header_text = f"Collection: {collection.get('name', 'Unknown')}"
                        break
            
            # Add a header item
            list_view.append(ListItem(Static(header_text.upper()), id="art_header"))
            
            articles = []
            
            # Load articles based on current view
            if self.current_view == "inbox":
                self.notify(message="Loading Inbox articles...", title="Loading")
                articles = self.client.get_library_by_category(category="inbox")
            elif self.current_view == "later":
                self.notify(message="Loading Later articles...", title="Loading")
                articles = self.client.get_library_by_category(category="later")
            elif self.current_view == "archive":
                self.notify(message="Loading Archive articles...", title="Loading")
                articles = self.client.get_library_by_category(category="archive")
            elif self.current_view == "collection" and self.current_collection_id:
                self.notify(message="Loading collection articles...", title="Loading")
                articles = self.client.get_collection_items(collection_id=self.current_collection_id)
            
            self.notify(message=f"Loaded {len(articles)} articles", title="Loading Complete")
            logger.debug(f"Loaded {len(articles)} articles for view '{self.current_view}'")
            
            # Add articles to the list view
            for article in articles:
                article_id = article.get("id")
                title = article.get("title", "Untitled")
                site_name = article.get("site_name", "")
                reading_progress = article.get("reading_progress", 0)
                is_read = article.get("read", False) or article.get("state") == "finished"
                saved_for_later = article.get("saved_for_later", False)
                
                # Format the title with metadata
                display_title = title
                if site_name:
                    display_title += f" ({site_name})"
                
                if reading_progress > 0 and reading_progress < 100:
                    display_title += f" - {reading_progress}%"
                elif is_read:
                    display_title += " - Read"
                    
                if saved_for_later and self.current_view != "later":
                    display_title += " - Later"
                
                # Create and append list item
                list_item = ListItem(Static(display_title), id=f"art_{article_id}")
                if is_read:
                    list_item.styles.text_style = "none"
                else:
                    list_item.styles.text_style = "bold"
                    
                list_view.append(list_item)
                
        except Exception as e:
            logger.error(f"Error refreshing articles: {e}")
            self.notify(message=f"Error refreshing articles: {e}", title="Error", severity="error")

    async def on_list_view_highlighted(self, message: Any) -> None:
        """Handle list view item highlighting."""
        highlighted_item = message.item
        if highlighted_item is None:
            return

        try:
            # Handle collection/category selection
            if hasattr(highlighted_item, "id") and highlighted_item.id is not None:
                if highlighted_item.id.startswith("col_"):
                    collection_id = highlighted_item.id.replace("col_", "")
                    self.current_collection_id = collection_id
                    self.current_view = "collection"
                    self.notify(message=f"Loading collection...", title="Collection")
                    await self.refresh_articles()
                elif highlighted_item.id == "lib_inbox":
                    self.current_collection_id = None
                    self.current_view = "inbox"
                    self.notify(message=f"Loading Inbox...", title="Inbox")
                    await self.refresh_articles()
                elif highlighted_item.id == "lib_later":
                    self.current_collection_id = None
                    self.current_view = "later"
                    self.notify(message=f"Loading Later...", title="Later")
                    await self.refresh_articles()
                elif highlighted_item.id == "lib_archive":
                    self.current_collection_id = None
                    self.current_view = "archive"
                    self.notify(message=f"Loading Archive...", title="Archive")
                    await self.refresh_articles()
                # Handle article selection
                elif highlighted_item.id.startswith("art_") and highlighted_item.id != "art_header":
                    article_id = highlighted_item.id.replace("art_", "")
                    self.current_article_id = article_id
                    await self.display_article(article_id=article_id)
        except Exception as e:
            logger.error(f"Error handling list view highlight: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    def action_debug_article(self) -> None:
        """Debug action to dump current article data to log file."""
        if not self.current_article:
            self.notify(message="No article selected", title="Debug")
            return
        
        try:
            # Log the full article data
            logger.debug(f"Full article data: {self.current_article}")
            
            # Notify the user
            self.notify(message="Article data logged to debug file", title="Debug")
        except Exception as e:
            logger.error(f"Error in debug action: {e}")
            
    async def action_move_to_inbox(self) -> None:
        """Move the current article to Inbox."""
        if not self.current_article_id:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        try:
            if self.client.move_to_category(article_id=self.current_article_id, category="inbox"):
                self.notify(message="Moved to Inbox", title="Article Status")
                await self.refresh_articles()
                
                # Refresh the article view to update metadata
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(message="Failed to move to Inbox", title="Error", severity="error")
        except Exception as e:
            logger.error(f"Error moving article to Inbox: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_move_to_later(self) -> None:
        """Move the current article to Later."""
        if not self.current_article_id:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        try:
            if self.client.move_to_category(article_id=self.current_article_id, category="later"):
                self.notify(message="Moved to Later", title="Article Status")
                await self.refresh_articles()
                
                # Refresh the article view to update metadata
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(message="Failed to move to Later", title="Error", severity="error")
        except Exception as e:
            logger.error(f"Error moving article to Later: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_toggle_archive(self) -> None:
        """Toggle archive status of the current article."""
        if not self.current_article_id:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        try:
            is_archived = self.current_article and self.current_article.get("archived", False)
            if is_archived:
                self.client.unarchive_article(article_id=self.current_article_id)
                self.notify(message="Unarchived article", title="Article Status")
            else:
                self.client.archive_article(article_id=self.current_article_id)
                self.notify(message="Archived article", title="Article Status")
                
            # Refresh the articles list to update the UI
            await self.refresh_articles()
            
            # Refresh the article view to update metadata
            if self.current_article_id:
                await self.display_article(article_id=self.current_article_id)
        except Exception as e:
            logger.error(f"Error toggling archive status: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")


    async def display_article(self, article_id: str) -> None:
        """Fetch and display article content."""
        try:
            # Fetch the article
            article = self.client.get_article(article_id=article_id)
            if not article:
                self.notify(message=f"Article not found: {article_id}", title="Error", severity="error")
                return
                
            self.current_article = article
            self.current_article_id = article_id
            
            # Get content from article
            title = article.get("title", "Untitled")
            
            # Try different possible content fields
            content = ""
            for content_field in ["content", "html", "text", "document"]:
                if content_field in article and article[content_field]:
                    content = article[content_field]
                    break
                    
            url = article.get("url", article.get("source_url", ""))
            author = article.get("author", article.get("creator", ""))
            site_name = article.get("site_name", article.get("domain", ""))
            summary = article.get("summary", "")
            published_date = article.get("published_date", "")
            word_count = article.get("word_count", 0)
            category = "Later" if article.get("saved_for_later", False) else "Inbox"
            category = "Archive" if article.get("archived", False) else category
            
            # Log article details for debugging
            logger.debug(f"Article ID: {article_id}")
            logger.debug(f"Article archived: {article.get('archived', False)}")
            logger.debug(f"Article saved_for_later: {article.get('saved_for_later', False)}")
            logger.debug(f"Determined category: {category}")
            
            # Format the markdown content
            header = f"# {title}\n\n"
            
            metadata = []
            if author:
                metadata.append(f"*By {author}*")
            if site_name:
                metadata.append(f"*From {site_name}*")
            if published_date:
                metadata.append(f"*Published: {published_date}*")
            if word_count:
                metadata.append(f"*{word_count} words*")
            metadata.append(f"*Category: {category}*")
            
            header += " | ".join(metadata) + "\n\n"
                
            if url:
                header += f"*[Original Article]({url})*\n\n"
                
            if summary:
                header += f"**Summary**: {summary}\n\n"
                
            header += "---\n\n"
            
            # Add placeholder if no content
            if not content:
                content = "*No content available. Try opening the article in browser.*"
                
            self.content_markdown = header + content
            
            # Display the content using our markdown view
            content_view = self.query_one("#content", ArticleViewer)
            content_view.update_content(self.content_markdown)
            
            if not content:
                # Log all keys to help understand the API response
                logger.debug(f"Full article data: {article}")
                
                # Notify the user
                self.notify(
                    message="No content found in this article. Try opening in browser.",
                    title="Article Content",
                    severity="warning"
                )
            
            # Auto-mark as read if enabled
            if self.configuration.auto_mark_read and not article.get("read", False) and not article.get("state") == "finished":
                self.client.mark_as_read(article_id=article_id)
                
                # Instead of refreshing the entire list, just update the current item's style
                if self.current_article_id:
                    try:
                        # Find the list item by ID and update its style
                        article_list_view: ListView = self.query_one("#articles", ListView)
                        for index, item in enumerate(article_list_view.children):
                            if hasattr(item, "id") and item.id == f"art_{self.current_article_id}":
                                item.styles.text_style = "none"
                                break
                    except Exception as e:
                        logger.debug(f"Error updating item style: {e}")
                        # Fall back to full refresh only if necessary
                        await self.refresh_articles()
                
        except Exception as e:
            logger.error(f"Error displaying article: {e}")
            self.notify(message=f"Error displaying article: {e}", title="Error", severity="error")


    def action_show_metadata(self) -> None:
        """Show detailed metadata for the current article."""
        if not self.current_article:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        try:
            # Extract all relevant metadata
            metadata = []
            metadata.append(f"Title: {self.current_article.get('title', 'Untitled')}")
            
            if "author" in self.current_article:
                metadata.append(f"Author: {self.current_article['author']}")
                
            if "site_name" in self.current_article:
                metadata.append(f"Source: {self.current_article['site_name']}")
                
            if "url" in self.current_article:
                metadata.append(f"URL: {self.current_article['url']}")
                
            if "published_date" in self.current_article:
                metadata.append(f"Published: {self.current_article['published_date']}")
                
            if "word_count" in self.current_article:
                metadata.append(f"Word Count: {self.current_article['word_count']}")
                
            if "reading_progress" in self.current_article:
                metadata.append(f"Reading Progress: {self.current_article['reading_progress']}%")
                
            category = "Later" if self.current_article.get("saved_for_later", False) else "Inbox"
            category = "Archive" if self.current_article.get("archived", False) else category
            metadata.append(f"Category: {category}")
            
            if "summary" in self.current_article and self.current_article["summary"]:
                metadata.append(f"\nSummary: {self.current_article['summary']}")
                
            # Additional metadata if available
            for key, value in self.current_article.items():
                if key not in ["title", "author", "site_name", "url", "published_date", 
                            "word_count", "reading_progress", "archived", "saved_for_later",
                            "summary", "content", "html", "text", "document"]:
                    if isinstance(value, (str, int, float, bool)) and value:
                        metadata.append(f"{key}: {value}")
            
            # Show metadata in a notification
            metadata_text = "\n".join(metadata)
            self.notify(
                title="Article Metadata",
                message=metadata_text,
                timeout=10,  # Longer timeout for more time to read
            )
            
        except Exception as e:
            logger.error(f"Error showing metadata: {e}")
            self.notify(message=f"Error showing metadata: {e}", title="Error", severity="error")

    def action_focus_next_pane(self) -> None:
        """Move focus to the next pane."""
        panes = ["collections", "articles", "content"]
        current_focus = self.focused
        if current_focus:
            current_id = current_focus.id
            if current_id in panes:
                next_index = (panes.index(current_id) + 1) % len(panes)
                next_pane = self.query_one(f"#{panes[next_index]}")
                next_pane.focus()

    def action_focus_previous_pane(self) -> None:
        """Move focus to the previous pane."""
        panes = ["collections", "articles", "content"]
        current_focus = self.focused
        if current_focus:
            current_id = current_focus.id
            if current_id in panes:
                previous_index = (panes.index(current_id) - 1) % len(panes)
                previous_pane = self.query_one(f"#{panes[previous_index]}")
                previous_pane.focus()

    def action_next_item(self) -> None:
        """Move to the next item in the current list."""
        current_focus = self.focused
        if current_focus and hasattr(current_focus, "action_cursor_down"):
            current_focus.action_cursor_down()

    def action_previous_item(self) -> None:
        """Move to the previous item in the current list."""
        current_focus = self.focused
        if current_focus and hasattr(current_focus, "action_cursor_up"):
            current_focus.action_cursor_up()

    def action_toggle_dark(self) -> None:
        """Toggle between dark and light theme."""
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"

    def action_toggle_help(self) -> None:
        """Show or hide the help screen."""
        if hasattr(self.screen, "id") and self.screen.id == "help":
            self.pop_screen()
        else:
            self.push_screen(HelpScreen())

    async def action_refresh(self) -> None:
        """Refresh all data from the API."""
        self.client.clear_cache()
        self.notify(message="Refreshing data...", title="Refresh")
        # Run workers sequentially
        await self.refresh_collections()
        await self.refresh_articles()
        if self.current_article_id:
            await self.display_article(article_id=self.current_article_id)
        self.notify(message="Refresh complete", title="Refresh")

    async def action_toggle_read(self) -> None:
        """Toggle read/unread status of the current article."""
        if not self.current_article_id:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        try:
            is_read = self.current_article and self.current_article.get("read", False)
            if is_read:
                self.client.mark_as_unread(article_id=self.current_article_id)
                self.notify(message="Marked as unread", title="Article Status")
            else:
                self.client.mark_as_read(article_id=self.current_article_id)
                self.notify(message="Marked as read", title="Article Status")
                
            # Refresh the articles list to update the UI
            await self.refresh_articles()
        except Exception as e:
            logger.error(f"Error toggling read status: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    def action_open_in_browser(self) -> None:
        """Open the current article in a web browser."""
        if not self.current_article:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        url = self.current_article.get("url")
        if not url:
            self.notify(message="No URL available for this article", title="Error", severity="warning")
            return
            
        try:
            webbrowser.open(url)
            self.notify(message="Opening in browser", title="Browser")
        except Exception as e:
            logger.error(f"Error opening browser: {e}")
            self.notify(message=f"Error opening browser: {e}", title="Error", severity="error")

    def action_clear(self) -> None:
        """Clear the content view."""
        self.content_markdown = "# Welcome to Readwise Reader TUI\n\nSelect an article to read."
        content_view = self.query_one("#content", ArticleViewer)
        content_view.update_content(self.content_markdown)
        self.current_article = None
        self.current_article_id = None

    async def action_debug_categories(self) -> None:
        """Debug action to test category functionality."""
        from ..utils.debug import inspect_readwise_categories, print_api_response
        
        self.notify(message="Running category debug...", title="Debug")
        
        try:
            # Test each category
            categories = ["inbox", "later", "archive"]
            
            for category in categories:
                logger.debug(f"Testing category: {category}")
                
                # First, try a direct API call
                logger.debug(f"Direct API call for {category}")
                if category == "archive":
                    response = self.client.session.get(f"{self.client.base_url}books/", 
                                                    params={"archived": True})
                elif category == "later":
                    response = self.client.session.get(f"{self.client.base_url}books/", 
                                                    params={"archived": False, "saved_for_later": True})
                else:  # inbox
                    response = self.client.session.get(f"{self.client.base_url}books/", 
                                                    params={"archived": False, "saved_for_later": False})
                    
                print_api_response(response, f"API response for {category}")
                
                # Then try our function
                logger.debug(f"Testing get_library_by_category for {category}")
                results = self.client.get_library_by_category(category=category)
                logger.debug(f"Got {len(results)} results for {category}")
                
                # Log a few sample articles
                for i, article in enumerate(results[:3]):
                    logger.debug(f"Sample article {i+1} for {category}:")
                    logger.debug(f"  ID: {article.get('id')}")
                    logger.debug(f"  Title: {article.get('title', 'Untitled')}")
                    logger.debug(f"  Archived: {article.get('archived', False)}")
                    logger.debug(f"  Saved for Later: {article.get('saved_for_later', False)}")
            
            self.notify(message="Category debug complete. Check log file.", title="Debug")
        except Exception as e:
            logger.error(f"Error in debug_categories: {e}")
            self.notify(message=f"Error in debug: {e}", title="Debug Error", severity="error")

    async def action_debug_reset_cache(self) -> None:
        """Debug action to reset the cache and reload everything."""
        self.notify(message="Resetting cache...", title="Debug")
        
        # Clear the client cache
        self.client.clear_cache()
        
        # Clear the current selection
        self.current_article = None
        self.current_article_id = None
        
        # Reset to inbox view
        self.current_collection_id = None
        self.current_view = "inbox"
        
        # Refresh collections and articles
        await self.refresh_collections()
        await self.refresh_articles()
        
        self.notify(message="Cache reset complete.", title="Debug")

    def action_debug_api(self) -> None:
        """Debug action to test the API directly."""
        if not hasattr(self.client, 'debug_api_call'):
            # Add the method to the client if not already there
            from ..utils.debug import debug_api_call
            setattr(self.client, 'debug_api_call', debug_api_call.__get__(self.client, type(self.client)))
        
        try:
            # Test basic user info
            self.notify(message="Testing API...", title="Debug")
            self.client.debug_api_call("user")
            
            # Test books endpoint with various parameters
            logger.debug("Testing books endpoint with no parameters")
            self.client.debug_api_call("books")
            
            logger.debug("Testing books endpoint with archived=true")
            self.client.debug_api_call("books", {"archived": True})
            
            logger.debug("Testing books endpoint with saved_for_later=true")
            self.client.debug_api_call("books", {"saved_for_later": True})
            
            logger.debug("Testing books endpoint with both parameters")
            self.client.debug_api_call("books", {"archived": False, "saved_for_later": False})
            
            self.notify(message="API tests complete. Check log file.", title="Debug")
        except Exception as e:
            logger.error(f"Error in debug_api: {e}")
            self.notify(message=f"Error in API debug: {e}", title="Debug Error", severity="error")

    def on_unmount(self) -> None:
        """Clean up resources when the app is closed."""
        if hasattr(self, "client"):
            self.client.close()
