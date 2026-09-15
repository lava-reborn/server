class lol.gpui.EditLabelInterface extends lol.gpui.GPUIObject
{
   var close_btn;
   var delete_btn;
   var dispatchEvent;
   var info_txt;
   var ok_btn;
   var title_txt;
   var vBar;
   var flag = false;
   function EditLabelInterface()
   {
      super();
      this.info_txt.text = "";
      this.doLater(this,"init");
   }
   function init()
   {
      this.ok_btn.addEventListener("click",this);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.delete_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.deleteLabel);
      this.vBar.scrollValue = 1;
      this.vBar.setSize(this.info_txt._height);
      this.vBar.addEventListener("position",this);
      this.vBar._visible = false;
      this.vBar.target = this.info_txt;
      this.vBar.upButton.addEventListener("scrollUp",this);
      this.vBar.downButton.addEventListener("scrollDown",this);
      this.vBar.upButton.addEventListener("stopScroll",this);
      this.vBar.downButton.addEventListener("stopScroll",this);
      this.info_txt.onScroller = mx.utils.Delegate.create(this,this.scrollText);
      lol.core.SceneShifter.hotKeyManager.addFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this.click);
      this.vBar.__position = 0;
      this.chekTextSize();
   }
   function close()
   {
      this.dispatchEvent({type:"canselMark"});
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.delete_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.deleteLabel);
      lol.core.SceneShifter.hotKeyManager.removeFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this.click);
   }
   function scrollUp()
   {
      this.flag = true;
   }
   function scrollDown()
   {
      this.flag = true;
   }
   function stopScroll()
   {
      this.flag = false;
   }
   function scrollText()
   {
      var _loc2_;
      if(this.vBar.sliderButton.onMouseMove == undefined && !this.flag)
      {
         _loc2_ = (this.info_txt.scroll - 1) * 100 / this.info_txt.maxscroll;
         if(this.info_txt.maxscroll == this.info_txt.scroll)
         {
            _loc2_ = 100;
         }
         if(_loc2_ < 100)
         {
            this.vBar.__position = _loc2_;
         }
         else
         {
            this.vBar.__position = 100;
         }
         this.chekTextSize();
      }
   }
   function chekTextSize()
   {
      if(this.info_txt.textHeight > this.info_txt._height)
      {
         this.vBar._visible = true;
      }
      else
      {
         this.vBar._visible = false;
      }
   }
   function position(obj)
   {
      this.vBar.scrollText();
   }
   function click(obj)
   {
      if(this.title.length > 0)
      {
         this.dispatchEvent({type:"applyMark",title:this.title,info:this.info,success:true});
         lol.core.SceneShifter.closeWindow("editLabel");
      }
   }
   function deleteLabel()
   {
      var _loc2_ = lol.core.SceneShifter.openNewWindow("query");
      _loc2_.content.addEventListener("click",this,this.__deleteLabel);
      _loc2_.content.alert_txt.text = "Удалить?";
   }
   function __deleteLabel(obj)
   {
      obj.target.removeEventListener("click",this,this.__deleteLabel);
      if(obj.success)
      {
         this.dispatchEvent({type:"deleteMark"});
         lol.core.SceneShifter.closeWindow("editLabel");
      }
      lol.core.SceneShifter.closeWindow("query");
   }
   function setMark(mark)
   {
      this.title = mark.title;
      this.info = mark.info;
   }
   function get title()
   {
      return this.title_txt.text;
   }
   function set title(str)
   {
      this.title_txt.text = str;
   }
   function get info()
   {
      return this.info_txt.text;
   }
   function set info(str)
   {
      this.info_txt.text = str;
   }
}
