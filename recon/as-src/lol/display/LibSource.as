class lol.display.LibSource extends lol.display.SpriteSource
{
   var cont_mc;
   var drawBitmap;
   function LibSource()
   {
      super();
   }
   function getBitmap(linkID)
   {
      var _loc2_ = this.cont_mc.attachMovie(linkID,"temp",0);
      var _loc3_ = this.drawBitmap();
      _loc2_.removeMovieClip();
      return _loc3_;
   }
   function hasItem(linkID)
   {
      var _loc2_ = this.cont_mc.attachMovie(linkID,"temp",0);
      if(_loc2_ != null)
      {
         _loc2_.removeMovieClip();
         return true;
      }
      return false;
   }
}
