class lol.core.globmap.DisplayMapLabel extends MovieClip
{
   var _markObj;
   var dispatchEvent;
   var title_txt;
   function DisplayMapLabel()
   {
      super();
      lol.events.LEventDispatcher.initialize(this);
      this.title_txt._visible = false;
   }
   function onPress()
   {
      this.dispatchEvent({type:"_moveToLabel"});
   }
   function onRollOver()
   {
      this.showInfo(true);
   }
   function onRollOut()
   {
      this.showInfo(false);
   }
   function showInfo(q)
   {
      this.title_txt._visible = q;
   }
   function set markObj(mark)
   {
      this._markObj = mark;
      this.info = this._markObj.info;
      this.title = this.markObj.title;
   }
   function get markObj()
   {
      return this._markObj;
   }
   function set info(str)
   {
   }
   function get info()
   {
      return this._markObj.info;
   }
   function set title(str)
   {
      this.title_txt.html = true;
      this.title_txt.autoSize = true;
      var _loc2_ = lol.utils.ParseString.replaceAll(str,"\\","");
      _loc2_ = lol.utils.ParseString.replaceAll(_loc2_,"%имя%",lol.core.Master.getInstance().gamer.playerInfo.name);
      this.title_txt.htmlText = "<I>" + _loc2_ + "</I>";
      this.title_txt._x = (- this.title_txt._width) / 2;
   }
   function get title()
   {
      return this._markObj.title;
   }
}
