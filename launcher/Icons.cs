// The icons, drawn from the concept's own SVG.
//
// The mock-up uses a handful of 24-unit line icons (plus a 48-unit avatar),
// all stroked, 1.5 units wide, round caps and joins. Rather than redraw each
// by hand in GDI+ calls -- and get each one slightly wrong -- the path data
// is kept verbatim and read by the small interpreter below, which knows
// exactly the commands those paths use: M L H V C S A Z, absolute and
// relative, and the circle element. An icon is then identical to the mock-up
// at any size, because it is the same drawing.
using System;
using System.Collections.Generic;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Globalization;

static class Icons
{
    // name -> primitives. "P" is a stroked path, "C" a stroked circle
    // (cx cy r), "F" a filled circle. The box is 24 unless the entry says
    // otherwise ("V48").
    static readonly Dictionary<string, string[]> Shapes = new Dictionary<string, string[]>
    {
        { "download", new[] { "P M12 3v12m-4-4 4 4 4-4M4 16v5h16v-5" } },
        { "arrow", new[] { "P M5 12h14m-5-5 5 5-5 5" } },
        { "external", new[] { "P M9 5H5v14h14v-4M13 5h6v6M19 5 10 14" } },
        { "pause", new[] { "P M8 5v14M16 5v14" } },
        { "play", new[] { "P m8 5 11 7-11 7Z" } },
        { "close", new[] { "P m6 6 12 12M18 6 6 18" } },
        { "check", new[] { "P m5 12 4 4L19 6" } },
        { "retry", new[] { "P M20 10a8 8 0 1 0-1 7M20 4v6h-6" } },
        { "alert", new[] { "P m12 3 10 18H2ZM12 9v5m0 3v.1" } },
        { "eye", new[] { "P M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12Z", "C 12 12 3" } },
        { "settings", new[] { "P M10 3h4l.5 2.4 1.7 1 2.4-.8 2 3.5-1.9 1.6v2.6l1.9 1.6-2 3.5-2.4-.8-1.7 1L14 21h-4l-.5-2.4-1.7-1-2.4.8-2-3.5 1.9-1.6v-2.6L3.4 9.1l2-3.5 2.4.8 1.7-1Z", "C 12 12 3" } },
        { "help", new[] { "C 12 12 9", "P M9.8 9a2.3 2.3 0 1 1 3.7 1.8c-1 .6-1.5 1.1-1.5 2.2", "F 12 16.5 .8" } },
        { "folder", new[] { "P M3 6.5V18a1 1 0 0 0 1 1h16a1 1 0 0 0 1-1V9a1 1 0 0 0-1-1h-8l-2-2.5H4a1 1 0 0 0-1 1Z" } },
        { "level", new[] { "P M6 19v-5M12 19V9M18 19V5" } },
        { "pin", new[] { "P M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11Z", "C 12 10 2.5" } },
        { "minimize", new[] { "P M5 12h14" } },
        { "window-close", new[] { "P m6.5 6.5 11 11m0-11-11 11" } },
        { "avatar", new[] { "V48", "P M10 38V24C10 11 17 6 24 6s14 5 14 18v14M15 36l2-12 7-5 7 5 2 12M17 24l7 4 7-4M21 33h6M10 38l14 5 14-5" } },
    };

    static readonly Dictionary<string, Shape> parsed = new Dictionary<string, Shape>();

    class Shape
    {
        public float Box = 24;
        public List<GraphicsPath> Strokes = new List<GraphicsPath>();
        public List<GraphicsPath> Fills = new List<GraphicsPath>();
    }

    /// <summary>Draw the icon with its top-left corner at (x, y), size units
    /// square, in logical pixels (the caller's transform applies). Stroke is
    /// the SVG stroke width in the icon's own units; 1.5 is the mock-up's.</summary>
    public static void Draw(Graphics g, string name, float x, float y, float size, Color c, float stroke)
    {
        Shape s = Get(name);
        if (s == null) return;
        float k = size / s.Box;
        GraphicsState st = g.Save();
        g.TranslateTransform(x, y);
        g.ScaleTransform(k, k);
        using (Pen p = new Pen(c, stroke))
        {
            p.StartCap = LineCap.Round;
            p.EndCap = LineCap.Round;
            p.LineJoin = LineJoin.Round;
            foreach (GraphicsPath gp in s.Strokes) g.DrawPath(p, gp);
        }
        using (SolidBrush b = new SolidBrush(c))
            foreach (GraphicsPath gp in s.Fills) g.FillPath(b, gp);
        g.Restore(st);
    }

    public static void Draw(Graphics g, string name, float x, float y, float size, Color c)
    {
        Draw(g, name, x, y, size, c, 1.5f);
    }

    static Shape Get(string name)
    {
        Shape s;
        if (parsed.TryGetValue(name, out s)) return s;
        string[] prims;
        if (!Shapes.TryGetValue(name, out prims)) return null;
        s = new Shape();
        foreach (string prim in prims)
        {
            if (prim.StartsWith("V"))
            {
                s.Box = float.Parse(prim.Substring(1), CultureInfo.InvariantCulture);
                continue;
            }
            string body = prim.Substring(2);
            switch (prim[0])
            {
                case 'P':
                    s.Strokes.Add(Path(body));
                    break;
                case 'C':
                case 'F':
                {
                    float[] v = Numbers(body);
                    GraphicsPath gp = new GraphicsPath();
                    gp.AddEllipse(v[0] - v[2], v[1] - v[2], v[2] * 2, v[2] * 2);
                    (prim[0] == 'C' ? s.Strokes : s.Fills).Add(gp);
                    break;
                }
            }
        }
        parsed[name] = s;
        return s;
    }

    static float[] Numbers(string s)
    {
        List<float> list = new List<float>();
        foreach (string part in s.Split(new[] { ' ', ',' }, StringSplitOptions.RemoveEmptyEntries))
            list.Add(float.Parse(part, CultureInfo.InvariantCulture));
        return list.ToArray();
    }

    // --- the path interpreter -----------------------------------------------

    static GraphicsPath Path(string d)
    {
        GraphicsPath gp = new GraphicsPath();
        List<float> nums = new List<float>();
        char cmd = ' ';
        int i = 0;
        PointF cur = PointF.Empty, start = PointF.Empty, lastCtrl = PointF.Empty;
        bool lastWasCurve = false;
        bool open = false;

        while (i < d.Length)
        {
            char ch = d[i];
            if (char.IsLetter(ch))
            {
                cmd = ch;
                i++;
                nums.Clear();
                if (cmd == 'Z' || cmd == 'z')
                {
                    if (open) { gp.CloseFigure(); open = false; }
                    cur = start;
                    lastWasCurve = false;
                    continue;
                }
                continue;
            }
            if (ch == ' ' || ch == ',') { i++; continue; }

            // A number: sign, digits, one dot, digits. SVG lets "-1 7" and
            // ".5.5" run together, so the scan stops at a second dot or a
            // sign that is not the first character.
            int j = i;
            if (d[j] == '-' || d[j] == '+') j++;
            bool dot = false;
            while (j < d.Length && (char.IsDigit(d[j]) || (d[j] == '.' && !dot)))
            {
                if (d[j] == '.') dot = true;
                j++;
            }
            if (j == i) { i++; continue; }  // something unexpected; skip it
            nums.Add(float.Parse(d.Substring(i, j - i), CultureInfo.InvariantCulture));
            i = j;

            // Enough numbers for the command? Then run it and keep the
            // command for the implicit repeat that follows.
            bool rel = char.IsLower(cmd);
            switch (char.ToUpperInvariant(cmd))
            {
                case 'M':
                    if (nums.Count == 2)
                    {
                        if (open) gp.StartFigure();
                        cur = At(rel, cur, nums[0], nums[1]);
                        start = cur;
                        open = true;
                        nums.Clear();
                        // Subsequent pairs are implicit line-tos.
                        cmd = rel ? 'l' : 'L';
                        lastWasCurve = false;
                    }
                    break;
                case 'L':
                    if (nums.Count == 2)
                    {
                        PointF to = At(rel, cur, nums[0], nums[1]);
                        gp.AddLine(cur, to);
                        cur = to;
                        nums.Clear();
                        lastWasCurve = false;
                    }
                    break;
                case 'H':
                    if (nums.Count == 1)
                    {
                        PointF to = new PointF(rel ? cur.X + nums[0] : nums[0], cur.Y);
                        gp.AddLine(cur, to);
                        cur = to;
                        nums.Clear();
                        lastWasCurve = false;
                    }
                    break;
                case 'V':
                    if (nums.Count == 1)
                    {
                        PointF to = new PointF(cur.X, rel ? cur.Y + nums[0] : nums[0]);
                        gp.AddLine(cur, to);
                        cur = to;
                        nums.Clear();
                        lastWasCurve = false;
                    }
                    break;
                case 'C':
                    if (nums.Count == 6)
                    {
                        PointF c1 = At(rel, cur, nums[0], nums[1]);
                        PointF c2 = At(rel, cur, nums[2], nums[3]);
                        PointF to = At(rel, cur, nums[4], nums[5]);
                        gp.AddBezier(cur, c1, c2, to);
                        lastCtrl = c2;
                        cur = to;
                        nums.Clear();
                        lastWasCurve = true;
                    }
                    break;
                case 'S':
                    if (nums.Count == 4)
                    {
                        // The first control point mirrors the previous one.
                        PointF c1 = lastWasCurve
                            ? new PointF(2 * cur.X - lastCtrl.X, 2 * cur.Y - lastCtrl.Y)
                            : cur;
                        PointF c2 = At(rel, cur, nums[0], nums[1]);
                        PointF to = At(rel, cur, nums[2], nums[3]);
                        gp.AddBezier(cur, c1, c2, to);
                        lastCtrl = c2;
                        cur = to;
                        nums.Clear();
                        lastWasCurve = true;
                    }
                    break;
                case 'A':
                    if (nums.Count == 7)
                    {
                        PointF to = At(rel, cur, nums[5], nums[6]);
                        Arc(gp, cur, nums[0], nums[1], nums[2], nums[3] != 0, nums[4] != 0, to);
                        cur = to;
                        nums.Clear();
                        lastWasCurve = false;
                    }
                    break;
                default:
                    nums.Clear();
                    break;
            }
        }
        return gp;
    }

    static PointF At(bool rel, PointF cur, float x, float y)
    {
        return rel ? new PointF(cur.X + x, cur.Y + y) : new PointF(x, y);
    }

    // SVG's endpoint arc turned into GDI+'s centre-and-angles arc, following
    // the conversion in the SVG specification (implementation notes F.6.5).
    // Only unrotated arcs occur in these icons, so phi is accepted and ignored.
    static void Arc(GraphicsPath gp, PointF p1, float rx, float ry, float phi,
                    bool large, bool sweep, PointF p2)
    {
        if (rx == 0 || ry == 0) { gp.AddLine(p1, p2); return; }
        rx = Math.Abs(rx); ry = Math.Abs(ry);
        double x1 = (p1.X - p2.X) / 2.0, y1 = (p1.Y - p2.Y) / 2.0;
        double lambda = (x1 * x1) / (rx * rx) + (y1 * y1) / (ry * ry);
        if (lambda > 1)
        {
            double s = Math.Sqrt(lambda);
            rx = (float)(rx * s); ry = (float)(ry * s);
        }
        double num = rx * rx * ry * ry - rx * rx * y1 * y1 - ry * ry * x1 * x1;
        double den = rx * rx * y1 * y1 + ry * ry * x1 * x1;
        double coef = den == 0 ? 0 : Math.Sqrt(Math.Max(0, num / den));
        if (large == sweep) coef = -coef;
        double cx1 = coef * (rx * y1 / ry), cy1 = coef * (-ry * x1 / rx);
        double cx = cx1 + (p1.X + p2.X) / 2.0, cy = cy1 + (p1.Y + p2.Y) / 2.0;

        double theta1 = Angle(1, 0, (x1 - cx1) / rx, (y1 - cy1) / ry);
        double dtheta = Angle((x1 - cx1) / rx, (y1 - cy1) / ry, (-x1 - cx1) / rx, (-y1 - cy1) / ry);
        if (!sweep && dtheta > 0) dtheta -= 2 * Math.PI;
        else if (sweep && dtheta < 0) dtheta += 2 * Math.PI;

        gp.AddArc((float)(cx - rx), (float)(cy - ry), rx * 2, ry * 2,
                  (float)(theta1 * 180 / Math.PI), (float)(dtheta * 180 / Math.PI));
    }

    static double Angle(double ux, double uy, double vx, double vy)
    {
        double dot = ux * vx + uy * vy;
        double len = Math.Sqrt((ux * ux + uy * uy) * (vx * vx + vy * vy));
        double a = Math.Acos(Math.Max(-1, Math.Min(1, len == 0 ? 1 : dot / len)));
        if (ux * vy - uy * vx < 0) a = -a;
        return a;
    }
}
