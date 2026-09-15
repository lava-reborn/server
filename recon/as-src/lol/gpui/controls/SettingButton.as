class lol.gpui.controls.SettingButton extends lol.gpui.GPUIObject
{
   var bg_btn;
   var dispatchEvent;
   var hotKeyManager;
   var key_txt;
   var tempKeyArr;
   var tempStr;
   var title_txt;
   var title_str = "default";
   var key_str = "default";
   var id = "settings";
   function SettingButton()
   {
      super();
      this.doLater("init");
      this.hotKeyManager = lol.core.SceneShifter.hotKeyManager;
   }
   function init()
   {
      var _loc2_ = this.hotKeyManager.getKeyInfo(this.id);
      this.bg_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.activate);
      this.initTitle();
   }
   function initTitle()
   {
      var _loc2_ = this.hotKeyManager.getKeyInfo(this.id);
      this.title_txt.text = _loc2_.about;
      this.key_txt.text = this.getKeyStr(_loc2_.keyCode);
      this.tempStr = this.key_txt.text;
   }
   function activate(obj)
   {
      if(obj.target.toggled)
      {
         this.inputKey();
      }
      else
      {
         this.saveKey();
      }
   }
   function inputKey()
   {
      this.tempStr = this.key_txt.text;
      this.key_txt.text = "...";
      this.key_txt.textColor = 2960424;
      this.keyListener(true);
      lol.core.SceneShifter.hotKeyManager.enabled = false;
      this.dispatchEvent({type:"input"});
   }
   function onKeyDown()
   {
      this.key_txt.text = this.getKeyStr(this.hotKeyManager.keyStack);
      var _loc3_ = this.hotKeyManager.keyStack;
      this.tempKeyArr = new Array();
      var _loc2_ = 0;
      while(_loc2_ < _loc3_.length)
      {
         this.tempKeyArr.push(_loc3_[_loc2_]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function saveKey()
   {
      if(this.key_txt.text == "...")
      {
         this.key_txt.text = this.tempStr;
      }
      else
      {
         this.dispatchEvent({type:"save",codeArr:this.tempKeyArr});
      }
      this.key_txt.textColor = 5328970;
      this.keyListener(false);
      lol.core.SceneShifter.hotKeyManager.enabled = true;
   }
   function keyListener(b)
   {
      if(b)
      {
         Key.addListener(this);
      }
      else
      {
         Key.removeListener(this);
      }
   }
   function getKeyStr(arr)
   {
      var _loc2_ = "";
      var _loc1_ = 0;
      while(_loc1_ < arr.length)
      {
         if(_loc1_ != 0)
         {
            _loc2_ += " + ";
         }
         _loc2_ += lol.utils.CharFromCode.getChar(arr[_loc1_]);
         _loc1_ = _loc1_ + 1;
      }
      return _loc2_;
   }
   function kill()
   {
      this.bg_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.activate);
   }
}
