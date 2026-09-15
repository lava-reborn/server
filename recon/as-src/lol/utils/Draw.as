class lol.utils.Draw
{
   function Draw()
   {
   }
   static function drawFillRect(target_mc, x, y, w, h, lth, lc, la, fc, fa)
   {
      target_mc.lineStyle(lth,lc,la);
      target_mc.beginFill(fc,fa);
      lol.utils.Draw.drawRect(target_mc,x,y,w,h);
      target_mc.endFill();
   }
   static function drawOutlineRect(target_mc, x, y, w, h, lth, lc, la)
   {
      target_mc.lineStyle(lth,lc,la);
      lol.utils.Draw.drawRect(target_mc,x,y,w,h);
   }
   static function drawRect(target_mc, x, y, w, h)
   {
      target_mc.moveTo(x,y);
      target_mc.lineTo(x + w,y);
      target_mc.lineTo(x + w,y + h);
      target_mc.lineTo(x,y + h);
      target_mc.lineTo(x,y);
   }
}
