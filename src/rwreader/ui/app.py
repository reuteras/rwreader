"""Simplified application class for rwreader."""

import logging
import sys
import webbrowser
from typing import Any, ClassVar, Dict, Optional

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header, ListItem, ListView, Static, Tree
from textual.containers import Horizontal, Vertical

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
        ("a", "move_to_archive", "Move to Archive"),
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
        
        # Debug - hidden from help
        ("ctrl+d", "debug_dump", None),  # Dump debug info
        ("ctrl+r", "debug_reset_cache", None),  # Reset cache
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
            self.current_category: str = "inbox"  # Default category
            self.content_markdown: str = "# Welcome to Readwise Reader TUI\n\nSelect an article to read."
            
            logger.debug("RWReader initialized")
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            print(f"Error: {e}")
            sys.exit(1)

    def compose(self) -> ComposeResult:
        """Compose the three-pane layout using ListView for navigation."""
        yield Header(show_clock=True)
        with Horizontal():
            yield ListView(id="navigation")
            with Vertical():
                yield ListView(id="articles")
                yield ArticleViewer(markdown=self.content_markdown, id="content")
        yield Footer()

    async def on_mount(self) -> None:
        """Load library data when the app is mounted."""
        logger.debug("App mounted")
        
        # Set up navigation list
        nav_list = self.query_one("#navigation", ListView)
        
        # Add header
        nav_list.append(ListItem(Static("LIBRARY"), id="nav_header"))
        
        # Add category items with data attributes
        inbox_item = ListItem(Static("Inbox"), id="nav_inbox")
        inbox_item.data = {"category": "inbox"}
        
        later_item = ListItem(Static("Later"), id="nav_later")
        later_item.data = {"category": "later"}
        
        archive_item = ListItem(Static("Archive"), id="nav_archive")
        archive_item.data = {"category": "archive"}
        
        # Add items to the list
        nav_list.append(inbox_item)
        nav_list.append(later_item)
        nav_list.append(archive_item)
        
        # Focus on the navigation list
        nav_list.focus()
        
        # Load initial articles
        await self.load_category("inbox")
        
        logger.debug("Initial app loading complete")

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        if event.node.data and "category" in event.node.data:
            category = event.node.data["category"]
            logger.debug(f"Category selected: {category}")
            
            # Update current category and load articles
            self.current_category = category
            await self.load_category(category)

    async def add_article_to_list(self, article: Dict[str, Any], list_view: ListView) -> None:
        """Add an article to the list view."""
        article_id = article.get("id")
        title = article.get("title", "Untitled")
        site_name = article.get("site_name", "")
        reading_progress = article.get("reading_progress", 0)
        is_read = article.get("read", False) or article.get("state") == "finished"
        
        # Format the title with metadata
        display_title = title
        if site_name:
            display_title += f" ({site_name})"
        
        # Add reading progress or read status
        if reading_progress > 0 and reading_progress < 100:
            display_title += f" - {reading_progress}%"
        elif is_read:
            display_title += " - Read"
            
        # Create the list item
        list_item = ListItem(Static(display_title), id=f"art_{article_id}")
        
        # Style based on read status
        if is_read:
            list_item.styles.text_style = "none"
        else:
            list_item.styles.text_style = "bold"
            
        # Add to the list
        list_view.append(list_item)

    async def on_list_view_highlighted(self, message: Any) -> None:
        """Handle list view item highlighting."""
        highlighted_item = message.item
        if not highlighted_item or not hasattr(highlighted_item, "id"):
            return
            
        # Check if this is a navigation item
        if highlighted_item.id.startswith("nav_") and highlighted_item.id != "nav_header":
            if hasattr(highlighted_item, "data") and isinstance(highlighted_item.data, dict) and "category" in highlighted_item.data:
                category = highlighted_item.data["category"]
                logger.debug(f"Category selected: {category}")
                
                # Update current category and load articles
                self.current_category = category
                await self.load_category(category)
        
        # Check if this is an article
        elif highlighted_item.id.startswith("art_") and highlighted_item.id != "header":
            article_id = highlighted_item.id.replace("art_", "")
            logger.debug(f"Article highlighted: {article_id}")
            
            # Load article content
            await self.display_article(article_id)

    async def display_article(self, article_id: str) -> None:
        """Fetch and display article content."""
        try:
            # Fetch the article
            article = self.client.get_article(article_id=article_id)
            if not article:
                self.notify(message=f"Article not found: {article_id}", title="Error", severity="error")
                return
                
            # Update state
            self.current_article = article
            self.current_article_id = article_id
            
            # Extract article details
            title = article.get("title", "Untitled")
            content = ""
            
            # Try different possible content fields
            for content_field in ["content", "html", "text", "document"]:
                if content_field in article and article[content_field]:
                    content = article[content_field]
                    break
            
            # Get metadata
            url = article.get("url", article.get("source_url", ""))
            author = article.get("author", article.get("creator", ""))
            site_name = article.get("site_name", article.get("domain", ""))
            summary = article.get("summary", "")
            published_date = article.get("published_date", "")
            word_count = article.get("word_count", 0)
            
            # Determine category
            category = "Archive" if article.get("archived", True) else (
                "Later" if article.get("saved_for_later", False) else "Inbox"
            )
            
            # Format markdown content
            header = f"# {title}\n\n"
            
            # Add metadata
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
            
            # Display content
            content_view = self.query_one("#content", ArticleViewer)
            content_view.update_content(self.content_markdown)
            
            # Auto-mark as read if enabled
            if self.configuration.auto_mark_read and not article.get("read", False) and not article.get("state") == "finished":
                logger.debug(f"Auto-marking article {article_id} as read")
                self.client.toggle_read(article_id=article_id, read=True)
                
                # Update item style without refreshing everything
                articles_list = self.query_one("#articles", ListView)
                for item in articles_list.children:
                    if hasattr(item, "id") and item.id == f"art_{article_id}":
                        item.styles.text_style = "none"
                        break
        except Exception as e:
            logger.error(f"Error displaying article: {e}")
            self.notify(message=f"Error displaying article: {e}", title="Error", severity="error")

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
            logger.debug(f"Opening article in browser: {url}")
            webbrowser.open(url)
            self.notify(message="Opening in browser", title="Browser")
        except Exception as e:
            logger.error(f"Error opening browser: {e}")
            self.notify(message=f"Error opening browser: {e}", title="Error", severity="error")

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
                
            # Determine category
            category = "Archive" if self.current_article.get("archived", True) else (
                "Later" if self.current_article.get("saved_for_later", False) else "Inbox"
            )
            metadata.append(f"Category: {category}")
            
            # Add summary if available
            if "summary" in self.current_article and self.current_article["summary"]:
                metadata.append(f"\nSummary: {self.current_article['summary']}")
            
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

    def action_clear(self) -> None:
        """Clear the content view."""
        self.content_markdown = "# Welcome to Readwise Reader TUI\n\nSelect an article to read."
        content_view = self.query_one("#content", ArticleViewer)
        content_view.update_content(self.content_markdown)
        self.current_article = None
        self.current_article_id = None
        logger.debug("Cleared content view")

    async def action_refresh(self) -> None:
        """Refresh all data from the API."""
        try:
            logger.debug("Refreshing data")
            
            # Clear the cache
            self.client.clear_cache()
            self.notify(message="Refreshing data...", title="Refresh")
            
            # Reload the current category
            await self.load_category(self.current_category)
            
            # Reload the article if one was selected
            if self.current_article_id:
                await self.display_article(article_id=self.current_article_id)
                
            self.notify(message="Refresh complete", title="Refresh")
        except Exception as e:
            logger.error(f"Error refreshing data: {e}")
            self.notify(message=f"Error refreshing data: {e}", title="Error", severity="error")

    def action_focus_next_pane(self) -> None:
        """Move focus to the next pane."""
        panes = ["navigation", "articles", "content"]
        current_focus = self.focused
        
        if current_focus:
            current_id = current_focus.id
            if current_id in panes:
                next_index = (panes.index(current_id) + 1) % len(panes)
                next_pane = self.query_one(f"#{panes[next_index]}")
                next_pane.focus()
                logger.debug(f"Focus moved to: {panes[next_index]}")

    def action_focus_previous_pane(self) -> None:
        """Move focus to the previous pane."""
        panes = ["navigation", "articles", "content"]
        current_focus = self.focused
        
        if current_focus:
            current_id = current_focus.id
            if current_id in panes:
                previous_index = (panes.index(current_id) - 1) % len(panes)
                previous_pane = self.query_one(f"#{panes[previous_index]}")
                previous_pane.focus()
                logger.debug(f"Focus moved to: {panes[previous_index]}")

    def action_next_item(self) -> None:
        """Move to the next item in the current list."""
        current_focus = self.focused
        
        if current_focus and hasattr(current_focus, "action_cursor_down"):
            # For normal listviews and other widgets with cursor_down
            current_focus.action_cursor_down()
        elif current_focus and current_focus.id == "navigation":
            # For the tree widget, we need to handle it specially
            tree = self.query_one("#navigation", Tree)
            # The tree widget handles its own navigation with keyboard events
            # So we can just pass this action through
            pass

    def action_previous_item(self) -> None:
        """Move to the previous item in the current list."""
        current_focus = self.focused
        
        if current_focus and hasattr(current_focus, "action_cursor_up"):
            # For normal listviews and other widgets with cursor_up
            current_focus.action_cursor_up()
        elif current_focus and current_focus.id == "navigation":
            # For the tree widget, we need to handle it specially
            tree = self.query_one("#navigation", Tree)
            # The tree widget handles its own navigation with keyboard events
            # So we can just pass this action through
            pass

    def action_toggle_dark(self) -> None:
        """Toggle between dark and light theme."""
        self.theme = "textual-dark" if self.theme == "textual-light" else "textual-light"
        logger.debug(f"Theme toggled to: {self.theme}")

    def action_toggle_help(self) -> None:
        """Show or hide the help screen."""
        if hasattr(self.screen, "id") and self.screen.id == "help":
            self.pop_screen()
            logger.debug("Help screen closed")
        else:
            self.push_screen(HelpScreen())
            logger.debug("Help screen opened")

    def action_debug_dump(self) -> None:
        """Dump debug information."""
        try:
            logger.debug("Dumping debug information")
            self.notify(message="Dumping debug information to log...", title="Debug")
            self.client.dump_debug_info()
            self.notify(message="Debug information dumped to log", title="Debug")
        except Exception as e:
            logger.error(f"Error dumping debug info: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_debug_reset_cache(self) -> None:
        """Reset cache and reload everything."""
        try:
            logger.debug("Resetting cache")
            self.notify(message="Resetting cache...", title="Debug")
            
            # Clear the client cache
            self.client.clear_cache()
            
            # Clear the current selection
            self.current_article = None
            self.current_article_id = None
            
            # Reload current category
            await self.load_category(self.current_category)
            
            self.notify(message="Cache reset complete", title="Debug")
        except Exception as e:
            logger.error(f"Error resetting cache: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")


    """Updates to app.py to work with our hybrid client."""

    async def load_category(self, category: str) -> None:
        """Load articles for the given category."""
        try:
            # Clear the current article
            self.current_article = None
            self.current_article_id = None
            
            # Update the articles list
            articles_list = self.query_one("#articles", ListView)
            await articles_list.clear()
            
            # Add category header
            header_text = category.capitalize()
            articles_list.append(ListItem(Static(f"{header_text.upper()} ARTICLES"), id="header"))
            
            # Notify user we're loading
            self.notify(message=f"Loading {header_text} articles...", title="Loading")
            
            # Get articles for the selected category
            articles = []
            if category == "inbox":
                articles = self.client.get_inbox()
            elif category == "later":
                articles = self.client.get_later()
            elif category == "archive":
                articles = self.client.get_archive()
            
            # Log article count
            logger.debug(f"Loaded {len(articles)} articles for {category}")
            
            # Add each article to the list
            for article in articles:
                await self.add_article_to_list(article, articles_list)
                
            # Show completed notification
            self.notify(message=f"Loaded {len(articles)} articles", title=f"{header_text}")
            
            # Clear the content pane
            content_view = self.query_one("#content", ArticleViewer)
            content_view.update_content("# Select an article to read")
        except Exception as e:
            logger.error(f"Error loading category {category}: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_move_to_inbox(self) -> None:
        """Move the current article to Inbox."""
        if not self.current_article_id:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        try:
            logger.debug(f"Moving article {self.current_article_id} to Inbox")
            
            if self.client.move_to_inbox(article_id=self.current_article_id):
                # Show success message
                self.notify(message="Moved to Inbox", title="Success")
                
                # Refresh if we're not already in the inbox
                if self.current_category != "inbox":
                    await self.load_category(self.current_category)
                    
                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(message="Failed to move to Inbox", title="Error", severity="error")
        except Exception as e:
            logger.error(f"Error moving to inbox: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_move_to_later(self) -> None:
        """Move the current article to Later."""
        if not self.current_article_id:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        try:
            logger.debug(f"Moving article {self.current_article_id} to Later")
            
            if self.client.move_to_later(article_id=self.current_article_id):
                # Show success message
                self.notify(message="Moved to Later", title="Success")
                
                # Refresh if we're not already in Later
                if self.current_category != "later":
                    await self.load_category(self.current_category)
                    
                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(message="Failed to move to Later", title="Error", severity="error")
        except Exception as e:
            logger.error(f"Error moving to later: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_move_to_archive(self) -> None:
        """Move the current article to Archive."""
        if not self.current_article_id:
            self.notify(message="No article selected", title="Error", severity="warning")
            return
            
        try:
            logger.debug(f"Moving article {self.current_article_id} to Archive")
            
            if self.client.move_to_archive(article_id=self.current_article_id):
                # Show success message
                self.notify(message="Moved to Archive", title="Success")
                
                # Refresh if we're not already in the Archive
                if self.current_category != "archive":
                    await self.load_category(self.current_category)
                    
                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(message="Failed to move to Archive", title="Error", severity="error")
        except Exception as e:
            logger.error(f"Error moving to archive: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

async def action_toggle_read(self) -> None:
    """Toggle read/unread status of the current article."""
    if not self.current_article_id or not self.current_article:
        self.notify(message="No article selected", title="Error", severity="warning")
        return
        
    try:
        # Determine current read status
        is_read = self.current_article.get("read", False) or self.current_article.get("state") == "finished"
        
        # Toggle status
        logger.debug(f"Toggling read status for article {self.current_article_id} to {not is_read}")
        
        if self.client.toggle_read(article_id=self.current_article_id, read=not is_read):
            # Show success message
            status = "read" if not is_read else "unread"
            self.notify(message=f"Marked as {status}", title="Success")
            
            # Update the article in the list without refreshing everything
            articles_list = self.query_one("#articles", ListView)
            for item in articles_list.children:
                if hasattr(item, "id") and item.id == f"art_{self.current_article_id}":
                    item.styles.text_style = "none" if not is_read else "bold"
                    break
            
            # Update current article's status
            self.current_article["read"] = not is_read
            self.current_article["state"] = "finished" if not is_read else "reading"
            
            # Refresh the article display
            await self.display_article(article_id=self.current_article_id)
        else:
            self.notify(message=f"Failed to toggle read status", title="Error", severity="error")
    except Exception as e:
        logger.error(f"Error toggling read status: {e}")
        self.notify(message=f"Error: {e}", title="Error", severity="error")


    def on_unmount(self) -> None:
        """Clean up resources when the app is closed."""
        if hasattr(self, "client"):
            logger.debug("Closing client")
            self.client.close()