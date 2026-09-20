// The window that says something went wrong.
//
// A MessageBox would do the job, and would look like it came from a different
// program. There are only four of these -- no res/ folder, no projector, no
// trust file, an unhandled fault -- and each one is the last thing the player
// sees, so it may as well be the same window as everything else.
using System;
using System.Drawing;
using System.Windows.Forms;

class Notice : Form
{
    const int W = 460, BAR = 40, PAD = 28;

    readonly string head, body;
    readonly PrimaryButton ok = new PrimaryButton();
    readonly WinButton close = new WinButton();
    int bodyHeight;

    Notice(string title, string text)
    {
        head = title;
        body = text;

        SetStyle(ControlStyles.AllPaintingInWmPaint | ControlStyles.UserPaint |
                 ControlStyles.OptimizedDoubleBuffer, true);
        FormBorderStyle = FormBorderStyle.None;
        StartPosition = FormStartPosition.CenterScreen;
        BackColor = Theme.BgBase;
        Text = "Lava Reborn";
        KeyPreview = true;
        Icon = Brand.AppIcon();
        ShowInTaskbar = true;

        // The message is the only thing that varies, so the window is measured
        // around it rather than given a size and hoping.
        using (Graphics g = CreateGraphics())
        {
            // Logical units throughout: the font is logical and MeasureString
            // does not see the paint transform.
            SizeF s = g.MeasureString(body, Theme.Body(14, false), W - PAD * 2);
            bodyHeight = (int)Math.Ceiling(s.Height) + 4;
        }

        int h = BAR + 26 + 28 + bodyHeight + 28 + 40 + 28;
        ClientSize = new Size(Theme.S(W), Theme.S(h));

        ok.Label = "Понятно";
        ok.Bounds = Theme.R(W - PAD - 130, h - 28 - 40, 130, 40);
        ok.Click += delegate { Close(); };
        Controls.Add(ok);

        close.IsClose = true;
        close.Bounds = Theme.R(W - 46, 0, 46, BAR);
        close.Click += delegate { Close(); };
        Controls.Add(close);
    }

    public static void Show(string title, string text)
    {
        try
        {
            Theme.Init();
            using (Notice n = new Notice(title, text)) n.ShowDialog();
        }
        catch
        {
            // Even the apology is allowed to fail on a machine this broken.
            MessageBox.Show(text, title, MessageBoxButtons.OK, MessageBoxIcon.Warning);
        }
    }

    protected override void OnKeyDown(KeyEventArgs e)
    {
        if (e.KeyCode == Keys.Escape || e.KeyCode == Keys.Enter) Close();
        base.OnKeyDown(e);
    }

    protected override void OnMouseDown(MouseEventArgs e)
    {
        if (e.Button == MouseButtons.Left && e.Y < Theme.S(BAR))
        {
            Native.ReleaseCapture();
            Native.SendMessage(Handle, 0xA1, 2, 0);
        }
        base.OnMouseDown(e);
    }

    protected override void OnPaint(PaintEventArgs e)
    {
        Graphics g = e.Graphics;
        Theme.Smooth(g);
        g.ScaleTransform(Theme.Scale, Theme.Scale);
        int w = (int)(ClientSize.Width / Theme.Scale);
        int h = (int)(ClientSize.Height / Theme.Scale);

        using (SolidBrush b = new SolidBrush(Theme.BgPanel))
            g.FillRectangle(b, 0, 0, w, BAR);
        using (SolidBrush b = new SolidBrush(Theme.Line))
            g.FillRectangle(b, 0, BAR - 1, w, 1);

        Brand.Draw(g, 16, (BAR - 20) / 2f, 20);
        Font mark = Theme.Display(14, true);
        float x = 46, my = (BAR - mark.GetHeight(g)) / 2f;
        x = Theme.Tracked(g, "LAVA", mark, Theme.Ink, x, my, 1.1f);
        Theme.Tracked(g, "REBORN", Theme.Display(14, false), Theme.InkMuted, x + 5, my, 1.1f);

        Theme.Text(g, head, Theme.Body(18, true), Theme.Ink, PAD, BAR + 26);

        using (SolidBrush b = new SolidBrush(Theme.InkMuted))
            g.DrawString(body, Theme.Body(14, false), b,
                         new RectangleF(PAD, BAR + 26 + 28, w - PAD * 2, bodyHeight + 8));

        using (Pen p = new Pen(Theme.Line, 1))
            g.DrawRectangle(p, 0, 0, w - 1, h - 1);
    }
}

static class Native
{
    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern bool ReleaseCapture();

    [System.Runtime.InteropServices.DllImport("user32.dll")]
    public static extern IntPtr SendMessage(IntPtr h, int msg, int wp, int lp);
}
