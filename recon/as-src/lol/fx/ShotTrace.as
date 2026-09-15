class lol.fx.ShotTrace
{
   var fx_mc;
   function ShotTrace()
   {
   }
   function traceShot(target, point0, point1)
   {
      var depth = target.getNextHighestDepth();
      this.fx_mc = target.createEmptyMovieClip("fx_mc" + depth,depth);
      with(this.fx_mc)
      {
         lineStyle(1,16777215,30);
         moveTo(point0.x,point0.y);
         lineTo(point1.x,point1.y);
      }
      var t = new lol.utils.Timeout(this,this.clearTrace,50);
   }
   function clearTrace(target)
   {
      this.fx_mc.clear();
      this.fx_mc.removeMovieClip();
   }
}
