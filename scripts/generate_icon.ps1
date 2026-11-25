param([string]$OutputDirectory = (Join-Path $PSScriptRoot '..\src\main\resources'))
Add-Type -AssemblyName System.Drawing
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
[IO.Directory]::CreateDirectory($OutputDirectory) | Out-Null
function New-ZiIcon([int]$Size) {
    $bitmap = [Drawing.Bitmap]::new($Size, $Size)
    $g = [Drawing.Graphics]::FromImage($bitmap)
    $g.SmoothingMode = [Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.ScaleTransform($Size / 256.0, $Size / 256.0)
    $g.Clear([Drawing.Color]::Transparent)
    $path = [Drawing.Drawing2D.GraphicsPath]::new()
    $path.AddArc(8,8,48,48,180,90); $path.AddArc(200,8,48,48,270,90)
    $path.AddArc(200,200,48,48,0,90); $path.AddArc(8,200,48,48,90,90); $path.CloseFigure()
    $background = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(255,23,25,34))
    $red = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(255,238,51,62))
    $white = [Drawing.SolidBrush]::new([Drawing.Color]::FromArgb(255,247,248,252))
    $border = [Drawing.Pen]::new([Drawing.Color]::FromArgb(255,238,51,62),8)
    $g.FillPath($background,$path); $g.DrawPath($border,$path)
    $points = [Drawing.PointF[]]@([Drawing.PointF]::new(40,60),[Drawing.PointF]::new(145,60),[Drawing.PointF]::new(145,87),[Drawing.PointF]::new(80,166),[Drawing.PointF]::new(145,166),[Drawing.PointF]::new(145,196),[Drawing.PointF]::new(40,196),[Drawing.PointF]::new(40,169),[Drawing.PointF]::new(105,90),[Drawing.PointF]::new(40,90))
    $g.FillPolygon($white,$points)
    $g.FillRectangle($white,168,60,42,136)
    $g.FillRectangle($red,40,218,105,7)
    $g.FillRectangle($red,168,218,42,7)
    $g.Dispose(); $path.Dispose(); $border.Dispose(); $background.Dispose(); $red.Dispose(); $white.Dispose()
    return ,$bitmap
}
$preview = New-ZiIcon 512
$preview.Save((Join-Path $OutputDirectory 'zi-ops.png'),[Drawing.Imaging.ImageFormat]::Png)
$preview.Dispose()
$sizes = @(16,24,32,48,64,128,256)
$frames = @()
foreach ($size in $sizes) {
    $bitmap = New-ZiIcon $size
    $stream = [IO.MemoryStream]::new()
    $bitmap.Save($stream,[Drawing.Imaging.ImageFormat]::Png)
    $frames += ,$stream.ToArray()
    $stream.Dispose(); $bitmap.Dispose()
}
$output = [IO.File]::Create((Join-Path $OutputDirectory 'ZI-Ops.ico'))
$writer = [IO.BinaryWriter]::new($output)
try {
    $writer.Write([uint16]0); $writer.Write([uint16]1); $writer.Write([uint16]$sizes.Count)
    $offset = 6 + 16 * $sizes.Count
    for ($i=0; $i -lt $sizes.Count; $i++) {
        $dimension = if ($sizes[$i] -eq 256) { 0 } else { $sizes[$i] }
        $writer.Write([byte]$dimension); $writer.Write([byte]$dimension); $writer.Write([byte]0); $writer.Write([byte]0)
        $writer.Write([uint16]1); $writer.Write([uint16]32); $writer.Write([uint32]$frames[$i].Length); $writer.Write([uint32]$offset)
        $offset += $frames[$i].Length
    }
    foreach ($frame in $frames) { $writer.Write([byte[]]$frame) }
} finally { $writer.Dispose() }
Write-Host 'Updated PNG and multi-resolution ICO.'
