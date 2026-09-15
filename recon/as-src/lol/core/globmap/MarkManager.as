class lol.core.globmap.MarkManager
{
   var markList;
   var marks_mc;
   static var questLinkage = "labelIcon_quest";
   static var labelLinkage = "labelIcon";
   static var questTakeLinkage = "labelIcon_questTake";
   static var QUEST_GET = "quest";
   static var QUEST_TAKE = "questTake";
   static var LABEL_TYPE = "label";
   static var CITY = "city";
   function MarkManager(mc)
   {
      this.marks_mc = mc;
   }
   function addMark(mark, type)
   {
      if(!this.markList)
      {
         this.markList = new Array();
      }
      var _loc3_ = this.marks_mc.getNextHighestDepth();
      var _loc2_ = this.marks_mc.attachMovie(lol.core.globmap.MarkManager[type + "Linkage"],"l" + _loc3_,_loc3_);
      _loc2_.markObj = mark;
      _loc2_.type = type;
      this.markList.push(_loc2_);
      return _loc2_;
   }
   function removeMark(mark)
   {
      var _loc2_ = this.getMarkNum(mark);
      var _loc3_ = this.markList[_loc2_];
      this.markList.splice(_loc2_,1);
      _loc3_.removeMovieClip();
   }
   function updateMark(mark)
   {
      var _loc4_ = this.getMarkNum(mark);
      var _loc2_ = this.markList[_loc4_];
      _loc2_.title = mark.title;
      _loc2_.info = mark.info;
   }
   function selectMark(mark)
   {
      for(var _loc2_ in this.markList)
      {
         this.markList[_loc2_].showInfo(false);
      }
      var _loc3_ = this.getMarkNum(mark);
      this.markList[_loc3_].showInfo(true);
   }
   function getMarkNum(mark)
   {
      var _loc2_ = 0;
      while(_loc2_ < this.markList.length)
      {
         if(this.markList[_loc2_].markObj == mark)
         {
            return _loc2_;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
}
