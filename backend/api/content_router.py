"""
邮件内容提取API路由
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Optional
from services.email_content_service import EmailContentService

router = APIRouter()

# 全局服务实例
content_service = EmailContentService()

@router.post("/extract")
async def start_content_extraction(request: dict) -> Dict:
    """开始提取旅行邮件内容"""
    try:
        limit = request.get('limit')  # None表示提取所有
        result = content_service.start_extraction(limit)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/extract/progress")
async def get_extraction_progress() -> Dict:
    """获取内容提取进度"""
    try:
        return content_service.get_extraction_progress()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/extract/stop")
async def stop_extraction() -> Dict:
    """停止内容提取"""
    try:
        message = content_service.stop_extraction()
        return {"stopped": True, "message": message}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_extraction_stats() -> Dict:
    """获取内容提取统计信息"""
    try:
        return content_service.get_extraction_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{email_id}")
async def get_email_content(email_id: str) -> Dict:
    """获取单个邮件的内容"""
    try:
        content = content_service.get_email_content(email_id)
        if not content:
            raise HTTPException(status_code=404, detail="Email content not found")
        return content
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{email_id}/view")
async def view_email_content(email_id: str):
    """查看邮件内容的HTML页面"""
    try:
        from fastapi.responses import HTMLResponse
        
        content = content_service.get_email_content(email_id)
        if not content:
            raise HTTPException(status_code=404, detail="Email content not found")
        
        # Create a rich HTML view
        html_content = content.get('content_html', '')
        text_content = content.get('content_text', '')
        subject = content.get('subject', 'No Subject')
        sender = content.get('sender', 'Unknown Sender')
        date = content.get('date', 'Unknown Date')
        classification = content.get('classification', 'unclassified')
        attachments = content.get('attachments', [])
        
        # If no HTML content, use text content
        if not html_content and text_content:
            html_content = f"<pre style='white-space: pre-wrap; font-family: Arial, sans-serif;'>{text_content}</pre>"
        
        # Build attachment list
        attachment_list = ""
        if attachments:
            attachment_list = "<div style='margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;'>"
            attachment_list += "<h3 style='margin: 0 0 10px 0; color: #333;'>📎 Attachments</h3>"
            for att in attachments:
                filename = att.get('filename', 'Unknown File')
                size = att.get('size', 0)
                size_str = f"{size} bytes" if size < 1024 else f"{size//1024} KB"
                attachment_list += f"<div style='margin: 5px 0; padding: 8px; background: white; border-radius: 3px; border-left: 3px solid #2196f3;'>"
                attachment_list += f"<strong>{filename}</strong> <span style='color: #666; font-size: 0.9em;'>({size_str})</span>"
                attachment_list += "</div>"
            attachment_list += "</div>"
        
        # Classification badge color
        classification_colors = {
            'flight': '#2196f3',
            'hotel': '#4caf50',
            'car_rental': '#ff9800',
            'train': '#9c27b0',
            'cruise': '#00bcd4',
            'tour': '#795548',
            'travel_insurance': '#607d8b',
            'flight_change': '#f44336',
            'hotel_change': '#ff5722',
            'other_travel': '#9e9e9e'
        }
        classification_color = classification_colors.get(classification, '#666')
        
        html_page = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{subject} - Email Content</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background: #f5f7fa;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 20px 30px;
                }}
                .header h1 {{
                    margin: 0 0 10px 0;
                    font-size: 1.5rem;
                }}
                .meta {{
                    display: flex;
                    gap: 20px;
                    margin-bottom: 10px;
                    font-size: 0.9rem;
                    opacity: 0.9;
                }}
                .classification {{
                    display: inline-block;
                    background: {classification_color};
                    color: white;
                    padding: 4px 12px;
                    border-radius: 15px;
                    font-size: 0.8rem;
                    font-weight: 500;
                    text-transform: uppercase;
                }}
                .content {{
                    padding: 30px;
                }}
                .email-content {{
                    border: 1px solid #e0e0e0;
                    border-radius: 5px;
                    overflow: hidden;
                }}
                .email-content iframe {{
                    width: 100%;
                    min-height: 400px;
                    border: none;
                }}
                .back-link {{
                    position: fixed;
                    top: 20px;
                    left: 20px;
                    background: rgba(0,0,0,0.8);
                    color: white;
                    padding: 10px 15px;
                    border-radius: 5px;
                    text-decoration: none;
                    font-size: 0.9rem;
                }}
                .back-link:hover {{
                    background: rgba(0,0,0,0.9);
                }}
            </style>
        </head>
        <body>
            <a href="javascript:window.close()" class="back-link">← Close</a>
            <div class="container">
                <div class="header">
                    <h1>{subject}</h1>
                    <div class="meta">
                        <span><strong>From:</strong> {sender}</span>
                        <span><strong>Date:</strong> {date}</span>
                    </div>
                    <span class="classification">{classification}</span>
                </div>
                <div class="content">
                    <div class="email-content">
                        {html_content}
                    </div>
                    {attachment_list}
                </div>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_page)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{email_id}/attachments")
async def view_email_attachments(email_id: str):
    """查看邮件附件的页面"""
    try:
        from fastapi.responses import HTMLResponse
        import os
        from pathlib import Path
        
        content = content_service.get_email_content(email_id)
        if not content:
            raise HTTPException(status_code=404, detail="Email content not found")
        
        attachments = content.get('attachments', [])
        subject = content.get('subject', 'No Subject')
        
        if not attachments:
            html_page = f"""
            <!DOCTYPE html>
            <html lang="en">
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>No Attachments - {subject}</title>
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                        margin: 0;
                        padding: 40px 20px;
                        background: #f5f7fa;
                        text-align: center;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 0 auto;
                        background: white;
                        padding: 40px;
                        border-radius: 10px;
                        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    }}
                    .back-link {{
                        position: fixed;
                        top: 20px;
                        left: 20px;
                        background: rgba(0,0,0,0.8);
                        color: white;
                        padding: 10px 15px;
                        border-radius: 5px;
                        text-decoration: none;
                        font-size: 0.9rem;
                    }}
                </style>
            </head>
            <body>
                <a href="javascript:window.close()" class="back-link">← Close</a>
                <div class="container">
                    <h1>📎 Attachments</h1>
                    <h2>{subject}</h2>
                    <p>This email has no attachments.</p>
                </div>
            </body>
            </html>
            """
            return HTMLResponse(content=html_page)
        
        # Build attachment list with download links
        attachment_items = ""
        data_root = Path(content_service.data_root)
        
        for att in attachments:
            filename = att.get('filename', 'Unknown File')
            size = att.get('size', 0)
            saved_path = att.get('saved_path', '')
            
            # Format file size
            if size < 1024:
                size_str = f"{size} bytes"
            elif size < 1024 * 1024:
                size_str = f"{size//1024} KB"
            else:
                size_str = f"{size//(1024*1024)} MB"
            
            # Check if file exists
            file_exists = False
            if saved_path:
                full_path = data_root / saved_path
                file_exists = full_path.exists()
            
            # File type icon
            ext = Path(filename).suffix.lower()
            icon = {
                '.pdf': '📄', '.doc': '📝', '.docx': '📝', '.txt': '📝',
                '.jpg': '🖼️', '.jpeg': '🖼️', '.png': '🖼️', '.gif': '🖼️',
                '.zip': '📦', '.rar': '📦', '.7z': '📦',
                '.csv': '📊', '.xlsx': '📊', '.xls': '📊'
            }.get(ext, '📄')
            
            download_link = ""
            if file_exists:
                download_link = f'<a href="/api/content/{email_id}/download/{filename}" target="_blank" style="color: #2196f3; text-decoration: none;">Download</a>'
            else:
                download_link = '<span style="color: #999;">File not available</span>'
            
            attachment_items += f"""
            <div style="display: flex; align-items: center; padding: 15px; margin: 10px 0; background: #f8f9fa; border-radius: 8px; border-left: 4px solid #2196f3;">
                <span style="font-size: 2rem; margin-right: 15px;">{icon}</span>
                <div style="flex: 1;">
                    <div style="font-weight: 600; color: #333; margin-bottom: 5px;">{filename}</div>
                    <div style="color: #666; font-size: 0.9rem;">{size_str}</div>
                </div>
                <div style="margin-left: 15px;">
                    {download_link}
                </div>
            </div>
            """
        
        html_page = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Attachments - {subject}</title>
            <style>
                body {{
                    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                    line-height: 1.6;
                    margin: 0;
                    padding: 20px;
                    background: #f5f7fa;
                }}
                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    background: white;
                    border-radius: 10px;
                    box-shadow: 0 2px 10px rgba(0,0,0,0.1);
                    overflow: hidden;
                }}
                .header {{
                    background: linear-gradient(135deg, #ff9800 0%, #f57c00 100%);
                    color: white;
                    padding: 20px 30px;
                    text-align: center;
                }}
                .header h1 {{
                    margin: 0 0 10px 0;
                    font-size: 1.8rem;
                }}
                .header h2 {{
                    margin: 0;
                    font-size: 1rem;
                    opacity: 0.9;
                    font-weight: normal;
                }}
                .content {{
                    padding: 30px;
                }}
                .back-link {{
                    position: fixed;
                    top: 20px;
                    left: 20px;
                    background: rgba(0,0,0,0.8);
                    color: white;
                    padding: 10px 15px;
                    border-radius: 5px;
                    text-decoration: none;
                    font-size: 0.9rem;
                }}
                .back-link:hover {{
                    background: rgba(0,0,0,0.9);
                }}
                .attachment-count {{
                    color: #666;
                    margin-bottom: 20px;
                    font-style: italic;
                }}
            </style>
        </head>
        <body>
            <a href="javascript:window.close()" class="back-link">← Close</a>
            <div class="container">
                <div class="header">
                    <h1>📎 Attachments</h1>
                    <h2>{subject}</h2>
                </div>
                <div class="content">
                    <div class="attachment-count">{len(attachments)} attachment(s) found</div>
                    {attachment_items}
                </div>
            </div>
        </body>
        </html>
        """
        
        return HTMLResponse(content=html_page)
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{email_id}/download/{filename}")
async def download_attachment(email_id: str, filename: str):
    """下载邮件附件"""
    try:
        from fastapi.responses import FileResponse
        from urllib.parse import unquote
        from pathlib import Path
        
        # URL decode filename
        filename = unquote(filename)
        
        # Get email content to find attachment
        content = content_service.get_email_content(email_id)
        if not content:
            raise HTTPException(status_code=404, detail="Email content not found")
        
        attachments = content.get("attachments", [])
        if not attachments:
            raise HTTPException(status_code=404, detail="No attachments found")
        
        # Find the specific attachment
        target_attachment = None
        for att in attachments:
            if att.get("filename", "") == filename:
                target_attachment = att
                break
        
        if not target_attachment:
            raise HTTPException(status_code=404, detail="Attachment not found")
        
        # Get file path
        saved_path = target_attachment.get("saved_path", "")
        if not saved_path:
            raise HTTPException(status_code=404, detail="Attachment file path not found")
        
        data_root = Path(content_service.data_root)
        file_path = data_root / saved_path
        
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Attachment file not found on disk")
        
        # Return file response
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/octet-stream"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

