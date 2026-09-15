class lol.gpui.MoneyPan extends lol.gpui.GPUIObject
{
   var gotoAndStop;
   var player;
   var textCharLeft;
   var textCharRight;
   var toolTip_btn;
   var _type = "afro";
   function MoneyPan()
   {
      super();
   }
   function setPlayer(_player)
   {
      this.player = _player;
      this.player.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.userInfoUpdate();
   }
   function kill()
   {
      this.player.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
   }
   function userInfoUpdate(obj)
   {
      var _loc2_;
      var _loc3_;
      if(this.type == "afro")
      {
         _loc2_ = this.player.attributes.afro;
         this.value = _loc2_;
      }
      else if(this.type == "gold")
      {
         _loc3_ = this.player.attributes.gold;
         this.value = _loc3_;
      }
   }
   function set type(value)
   {
      this._type = value;
   }
   function get type()
   {
      return this._type;
   }
   function set value(money)
   {
      this.textCharLeft.alignText = "left";
      this.textCharLeft.attachText = "moneyChar";
      this.textCharLeft.letterSpace = 1;
      this.textCharRight.alignText = "left";
      this.textCharRight.attachText = "moneyChar";
      this.textCharRight.letterSpace = 1;
      var _loc3_;
      var _loc2_;
      if(this.type == "afro")
      {
         this.gotoAndStop(1);
         this.textCharLeft.showValue(money,7);
         this.toolTip_btn.hintTitle_str = "Ваш счет в Афро";
      }
      else
      {
         this.gotoAndStop(2);
         _loc3_ = Math.floor(money / 100);
         _loc2_ = money % 100;
         this.textCharLeft.showValue(_loc3_,3);
         this.textCharRight.showValue(_loc2_,2);
         this.toolTip_btn.hintTitle_str = "Ваш счет в Золоте";
      }
      this.toolTip_btn.useHandCursor = false;
   }
}
