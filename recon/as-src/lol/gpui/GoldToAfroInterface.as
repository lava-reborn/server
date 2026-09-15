class lol.gpui.GoldToAfroInterface extends lol.gpui.GPUIObject
{
   var addGold_btn;
   var afro_max;
   var afro_txt;
   var bankAccount;
   var close_btn;
   var convert_btn;
   var dispatchEvent;
   var getURL;
   var gold;
   var gold_txt;
   var kurs;
   var kurs_txt;
   var bufer = "0";
   function GoldToAfroInterface()
   {
      super();
      this.gold = lol.core.Master.getInstance().gamer.attributes.gold / 100;
      this.kurs = Number(lol.core.GConstatns.getGoldToAfroRate());
      this.kurs_txt.text = "G 1 = A " + String(this.kurs);
      this.doLater("init");
   }
   function init()
   {
      this.bankAccount = lol.core.Master.getInstance().gamer.bankAccount;
      this.bankAccount.addEventListener("convert",this);
      this.afro_txt.onChanged = mx.utils.Delegate.create(this,this.onChangedAfro);
      this.afro_max = Math.ceil(this.gold * this.kurs);
      this.gold_txt.onChanged = mx.utils.Delegate.create(this,this.onChangedGold);
      this.close_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.convert_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.convert);
      this.addGold_btn.addEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addGold);
      this.afro_txt.restrict = "0-9";
      this.gold_txt.restrict = "0-9 .";
      lol.core.SceneShifter.hotKeyManager.addFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.addEventListener(lol.services.HotKeyEvent.APPLY,this,this.convert);
      lol.core.SceneShifter.hotKeyManager.enabled = false;
   }
   function close()
   {
      this.dispatchEvent({type:"closeWindow"});
   }
   function kill()
   {
      this.close_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.close);
      this.convert_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.convert);
      this.bankAccount.removeEventListener("convert",this);
      this.addGold_btn.removeEventListener(lol.gpui.controls.GPUIButton.RELEASE_EVENT,this,this.addGold);
      lol.core.SceneShifter.hotKeyManager.removeFilter("dialogue");
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.CANCEL,this,this.close);
      lol.core.SceneShifter.hotKeyManager.removeEventListener(lol.services.HotKeyEvent.APPLY,this,this.convert);
      lol.core.SceneShifter.hotKeyManager.enabled = true;
   }
   function convert()
   {
      var _loc2_ = Number(this.gold_txt.text) * 100;
      lol.core.Master.getInstance().gamer.bankAccount.addEventListener("converted",this);
      lol.core.Master.getInstance().gamer.bankAccount.convertGoldToAfro(_loc2_);
   }
   function converted(obj)
   {
      lol.core.Master.getInstance().gamer.bankAccount.removeEventListener("converted",this);
      var _loc2_ = obj.success;
      var _loc3_;
      if(!_loc2_)
      {
         _loc3_ = lol.core.SceneShifter.openNewWindow("alert");
         _loc3_.content.label = "Не удалось произвести операцию";
      }
      this.close();
   }
   function onChangedAfro()
   {
      if(this.afro_txt.text == "")
      {
         this.bufer = "0";
         this.afro_txt.text = "";
      }
      else if(Number(this.afro_txt.text) <= this.afro_max)
      {
         this.bufer = String(this.checkNumber(Number(this.afro_txt.text) / this.kurs));
      }
      else
      {
         this.afro_txt.text = String(this.afro_max);
         this.bufer = String(Number(this.afro_txt.text) / this.kurs);
      }
      this.gold_txt.text = this.bufer;
   }
   function checkNumber(num)
   {
      num = Math.ceil(num * 100) / 100;
      return num;
   }
   function onChangedGold()
   {
      if(this.check(this.gold_txt.text))
      {
         if(this.gold_txt.text == "")
         {
            this.bufer = "";
            this.afro_txt.text = "0";
         }
         else if(this.gold_txt.text == ".")
         {
            this.bufer = ".";
            this.afro_txt.text = "0";
         }
         else if(Number(this.gold_txt.text) > this.gold)
         {
            this.bufer = this.gold;
            this.gold_txt.text = this.gold;
            this.afro_txt.text = String(Math.ceil(Number(this.bufer) * this.kurs));
         }
         else
         {
            this.bufer = this.gold_txt.text;
            this.afro_txt.text = String(Math.ceil(Number(this.bufer) * this.kurs));
         }
      }
      else
      {
         this.gold_txt.text = this.bufer;
      }
   }
   function check(str)
   {
      var _loc1_ = str.indexOf(".",0);
      if(_loc1_ == -1)
      {
         return true;
      }
      var _loc3_ = str.indexOf(".",_loc1_ + 1);
      if(_loc3_ != -1)
      {
         return false;
      }
      var _loc4_ = str.substring(_loc1_ + 1,str.length);
      if(_loc4_.length > 2)
      {
         return false;
      }
      return true;
   }
   function addGold()
   {
      var _loc2_ = lol.core.SceneShifter._ref.getProfileUrl();
      this.getURL(_loc2_,"_blank");
   }
}
