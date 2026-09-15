class lol.gpui.FeedBackInterface extends lol.gpui.GPUIObject
{
   var close_btn;
   var description_txt;
   var dispatchEvent;
   var scrollBar;
   var send_btn;
   var theme_txt;
   function FeedBackInterface()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.send_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.send);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.scrollBar.scrollValue = 1;
      this.scrollBar.setSize(this.description_txt._height);
      this.scrollBar.target = this.description_txt;
      this.scrollBar._visible = false;
      this.scrollBar.addEventListener("position",this);
      this.description_txt.onChanged = mx.utils.Delegate.create(this,this.onChangedText);
      this.theme_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.theme_txt.onKillFocus = mx.utils.Delegate.create(this,this.unBlockHotKeys);
      this.description_txt.onSetFocus = mx.utils.Delegate.create(this,this.blockHotKeys);
      this.description_txt.onKillFocus = mx.utils.Delegate.create(this,this.unBlockHotKeys);
      this.description_txt.text = "";
      this.theme_txt.tabIndex = 0;
      this.description_txt.tabIndex = 1;
      Selection.setFocus(this.theme_txt);
      lol.core.SceneShifter.hotKeyManager.addFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this.send);
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.send_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.send);
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      lol.core.SceneShifter.hotKeyManager.removeFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this.send);
   }
   function blockHotKeys()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = false;
   }
   function unBlockHotKeys()
   {
      lol.core.SceneShifter.hotKeyManager.enabled = true;
   }
   function onChangedText()
   {
      var _loc2_ = (this.description_txt.scroll - 1) * 100 / this.description_txt.maxscroll;
      if(this.description_txt.maxscroll == this.description_txt.scroll)
      {
         _loc2_ = 100;
      }
      if(_loc2_ < 100)
      {
         this.scrollBar.__position = _loc2_;
      }
      else
      {
         this.scrollBar.__position = 100;
      }
      this.chekTextSize();
   }
   function chekTextSize()
   {
      if(this.description_txt.textHeight > this.description_txt._height)
      {
         this.scrollBar._visible = true;
      }
      else
      {
         this.scrollBar._visible = false;
      }
   }
   function send()
   {
      var _loc5_;
      var _loc3_;
      var _loc2_;
      var _loc6_;
      var _loc7_;
      var _loc4_;
      if(this.theme_txt.text != "" && this.description_txt.text != "")
      {
         _loc5_ = this.theme_txt.text;
         _loc3_ = this.description_txt.text;
         _loc2_ = lol.core.SceneShifter._ref.login;
         _loc6_ = lol.core.Master.getInstance().session.hash;
         _loc7_ = String(flash.external.ExternalInterface.call("userRequest",_loc2_,_loc6_,_loc5_,_loc3_));
         _loc4_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc4_.content.label = "Сообщение отправлено. На Ваш почтовый ящик выслано уведомление.";
         this.close();
      }
   }
}
