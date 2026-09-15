class lol.gpui.SlideItem extends lol.gpui.GPUIObject
{
   var _data;
   var _label;
   var bg;
   var currentSkill;
   var dispatchEvent;
   var progressBar;
   var skillNum;
   function SlideItem()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.bg.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.click);
   }
   function click(obj)
   {
      if(obj.target.toggled)
      {
         this._label.textColor = 11183515;
      }
      else
      {
         this._label.textColor = 9538948;
      }
      this.dispatchEvent({type:"click"});
   }
   function set data(obj)
   {
      this._data = obj;
      var _loc2_ = obj;
      this.skillNum = _loc2_.level;
      this.currentSkill = _loc2_.currentValue;
      var _loc3_ = new TextFormat();
      _loc3_.bold = true;
      this.progressBar.skillNum.num_txt.text = _loc2_.currentValue + "%";
      this.progressBar.skillNum.num_txt.setTextFormat(_loc3_);
      if(this.skillNum < 0)
      {
         this.progressBar.line.gotoAndStop(2);
      }
      else
      {
         this.progressBar.gotoAndStop(this.currentSkill + 2);
      }
   }
   function get data()
   {
      return this._data;
   }
   function get toggled()
   {
      return this.bg.toggled;
   }
   function set toggled(b)
   {
      this.bg.toggled = b;
      if(b)
      {
         this._label.textColor = 11183515;
      }
      else
      {
         this._label.textColor = 9538948;
      }
   }
   function set label(str)
   {
      this._label.text = str;
   }
}
