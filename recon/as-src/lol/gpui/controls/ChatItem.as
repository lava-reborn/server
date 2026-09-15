class lol.gpui.controls.ChatItem extends lol.gpui.GPUIObject
{
   var _data;
   var backButton;
   var dispatchEvent;
   var startChat_btn;
   var startInspect_btn;
   function ChatItem()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.backButton.addEventListener("rollOver",this);
      this.backButton.addEventListener("rollOut",this);
      this.backButton.addEventListener("releaseOutside",this);
      this.backButton.useHandCursor = false;
      this.startChat_btn.addEventListener("rollOver",this);
      this.startChat_btn.addEventListener("rollOut",this);
      this.startChat_btn.addEventListener("releaseOutside",this);
      this.startInspect_btn.addEventListener("rollOver",this);
      this.startInspect_btn.addEventListener("rollOut",this);
      this.startInspect_btn.addEventListener("releaseOutside",this);
      this.startChat_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.startChat);
      this.startInspect_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.startInspect);
   }
   function rollOver(obj)
   {
      this.backButton.gotoAndStop(2);
      this.backButton._label.textColor = this.backButton.style.color1;
   }
   function rollOut(obj)
   {
      this.backButton.gotoAndStop(1);
      this.backButton._label.textColor = this.backButton.style.color0;
   }
   function releaseOutside(obj)
   {
      this.backButton.gotoAndStop(1);
      this.backButton._label.textColor = this.backButton.style.color0;
   }
   function startChat(obj)
   {
      this.dispatchEvent({type:"startChat"});
   }
   function startInspect(obj)
   {
      this.dispatchEvent({type:"startInspect"});
   }
   function set label(l)
   {
      this.doLater("setLabel",[l]);
   }
   function setLabel(l)
   {
      this.backButton.label = l;
      this.backButton._label.autoSize = false;
   }
   function get label()
   {
      return this.backButton.label;
   }
   function set data(d)
   {
      this._data = d;
   }
   function get data()
   {
      return this._data;
   }
   function setStyle(obj)
   {
      this.backButton.setStyle(obj);
   }
}
