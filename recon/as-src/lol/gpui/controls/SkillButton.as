class lol.gpui.controls.SkillButton extends lol.gpui.GPUIObject
{
   var _width;
   var bg;
   var btn;
   var cont;
   var createEmptyMovieClip;
   var getNextHighestDepth;
   var mask;
   var onEnterFrameMov;
   var skill;
   var skillNum;
   function SkillButton()
   {
      super();
      this.mask._width = this._width;
      this.mask._alpha = 0;
      this.mask._height = 1;
      this.onEnterFrameMov = this.createEmptyMovieClip("onEnterFrameMov",this.getNextHighestDepth());
      this.bg.useHandCursor = false;
      this.bg.onPress = function()
      {
      };
   }
   function openContent(link)
   {
      var _loc4_;
      if(link)
      {
         _loc4_ = this.createEmptyMovieClip("cont",this.getNextHighestDepth());
         this.cont = this.cont.attachMovie(link,link,this.cont.getNextHighestDepth());
      }
      else
      {
         this.cont = this.createEmptyMovieClip("cont",this.getNextHighestDepth());
      }
      var _loc3_ = new lol.utils.Timeout(this,this.checkSize,200);
   }
   function checkSize()
   {
      this.cont._y = Math.round(Math.abs((this.bg._height - this.cont.content._height) / 2) + this.btn._height - 3);
      this.cont._x = Math.round((this.bg._width - this.cont._width) / 2);
   }
   function showSkill(num)
   {
      this.skillNum = num;
      this.skill.gotoAndStop(num);
   }
}
