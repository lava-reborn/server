class lol.gpui.gamehelp.GameHelpWindow extends lol.gpui.GPUIObject
{
   var GameHelpWindow_CloseBtn;
   var cont;
   var dispatchEvent;
   var dontShowHelp;
   var picPan;
   var textPan;
   var title;
   function GameHelpWindow()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      this.GameHelpWindow_CloseBtn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      var _loc2_ = lol.gpui.gamehelp.GameHelpMessageManager.getInstance();
      var _loc4_;
      var _loc3_;
      var _loc5_;
      if(_loc2_)
      {
         this.title.text = _loc2_.title;
         this.cont = this.textPan.fillContent();
         this.textPan.setSize(330,180);
         _loc4_ = this.cont.attachMovie("questdescriptionText","questdescriptionText" + this.cont.getNextHighestDepth(),this.cont.getNextHighestDepth());
         _loc3_ = _loc4_.description_txt;
         _loc3_._width = 330;
         _loc3_.autoSize = true;
         _loc3_.wordWrap = true;
         _loc3_.multiline = true;
         _loc3_.html = true;
         _loc3_.htmlText = _loc2_.htmlText;
         _loc5_ = lol.services.SSEmulator.getHintsImage(_loc2_.pic_id);
         this.picPan = lol.display.DisplaySprite.create(this.picPan,_loc2_.pic_id + "_hint_image",0);
         this.picPan.autoSize = true;
         this.picPan.display(_loc2_.pic_id + "_hint_image",_loc5_);
         this.textPan.chekSize();
      }
      this.dontShowHelp.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.showGameHelp);
      this.dontShowHelp.toggled = !lol.gpui.UserSettings.getSetting(lol.gpui.UserSettings.SHOW_GAME_HELP);
   }
   function showGameHelp(obj)
   {
      lol.gpui.UserSettings.setSetting(lol.gpui.UserSettings.SHOW_GAME_HELP,!obj.target.toggled);
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.GameHelpWindow_CloseBtn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      lol.core.SceneShifter.closeWindow("annotation","all");
      lol.core.SceneShifter.hotKeyManager.removeFilter("quest");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
   }
}
