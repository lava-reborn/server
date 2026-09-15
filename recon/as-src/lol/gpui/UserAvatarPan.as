class lol.gpui.UserAvatarPan extends lol.gpui.GPUIObject
{
   var av_cont;
   var caunter_mc;
   var gamerName_txt;
   var healthBar;
   var healthBarState;
   var healthBar_btn;
   var health_btn;
   var level_txt;
   var my_fmt;
   var player;
   var playerID;
   var rep_icon;
   var staminaBar;
   var staminaBarState;
   var staminaBar_btn;
   var stamina_btn;
   var matrix = new Array();
   function UserAvatarPan()
   {
      super();
      this.doLater("init");
   }
   function init()
   {
      var _loc3_ = lol.core.Master.getInstance();
      this.player = _loc3_.getPlayer(this.playerID);
      this.my_fmt = new TextFormat();
      this.my_fmt.bold = true;
      this.level_txt.text = String(this.player.attributes.level);
      this.level_txt.setTextFormat(this.my_fmt);
      this.player.addEventListener(lol.events.PlayerEvent.UPDATE_STATE,this,this.userStateUpdate);
      this.player.attributes.addEventListener(lol.events.PlayerEvent.UPDATE_PARAMS,this,this.rpUpdate);
      this.player.reputations.addEventListener(lol.core.player.Reputation.PersReputations.INCREASE_REP_LEVEL,this,this.repUpdate);
      var _loc4_ = this.player.playerInfo.name;
      this.gamerName_txt.text = _loc4_;
      this.gamerName_txt.setTextFormat(this.my_fmt);
      this.rep_icon.hintTitle_str = "Убить всех людей!";
      var _loc2_ = Number(this.player.reputations.getReputation(0).value_bonus) + 1;
      if(!isNaN(_loc2_))
      {
         this.rep_icon.gotoAndStop(_loc2_);
      }
      else
      {
         this.rep_icon.gotoAndStop(0);
      }
      if(_loc2_ > 1)
      {
         this.level_txt._x = 100;
      }
      else
      {
         this.level_txt._x = 93;
      }
      this.doLater("userStateUpdate");
      this.caunter_mc.textHealth.attachText = "textChar";
      this.caunter_mc.textStamina.attachText = "textChar";
      this.health_btn = this.caunter_mc.health_btn;
      this.stamina_btn = this.caunter_mc.stamina_btn;
      this.health_btn.useHandCursor = this.stamina_btn.useHandCursor = false;
      this.healthBar_btn.useHandCursor = this.staminaBar_btn.useHandCursor = false;
      this.loadAvatar();
   }
   function loadAvatar()
   {
      var _loc2_ = this.player.playerInfo.avatar.id;
      var _loc3_ = lol.services.SSEmulator.getAvatarURL(_loc2_,1);
      var _loc4_ = lol.display.DisplaySprite.create(this.av_cont,"av",0);
      _loc4_.display("big_avatar" + _loc2_,_loc3_);
   }
   function userStateUpdate(obj)
   {
      this.healthDelay();
      this.staminaDelay();
      this.level_txt.text = String(this.player.attributes.level);
      this.level_txt.setTextFormat(this.my_fmt);
   }
   function rpUpdate(obj)
   {
      this.healthDelay();
      this.staminaDelay();
      if(this.player.attributes.level != undefined)
      {
         this.level_txt.text = String(this.player.attributes.level);
         this.level_txt.setTextFormat(this.my_fmt);
      }
   }
   function repUpdate(obj)
   {
      var _loc2_ = obj.value;
      var _loc3_;
      if(_loc2_ != undefined && !isNaN(_loc2_))
      {
         _loc3_ = Number(_loc2_) + 1;
         this.rep_icon.gotoAndStop(_loc3_);
         if(_loc3_ > 1)
         {
            this.level_txt._x = 100;
         }
         else
         {
            this.level_txt._x = 93;
         }
      }
      else
      {
         this.rep_icon.gotoAndStop(0);
      }
   }
   function showHealth(p)
   {
      var _loc2_ = 101 - p;
      this.healthBar.gotoAndStop(_loc2_);
      this.healthBarState.gotoAndStop(_loc2_);
   }
   function healthDelay()
   {
      var _loc2_ = Math.round(100 * this.player.health / this.player.maxHealth);
      this.showHealth(_loc2_);
      this.caunter_mc.textHealth.showValue(this.player.health);
   }
   function showStamina(p)
   {
      var _loc2_ = 101 - p;
      this.staminaBar.gotoAndStop(_loc2_);
      this.staminaBarState.gotoAndStop(_loc2_);
   }
   function staminaDelay()
   {
      var _loc2_ = Math.round(100 * this.player.stamina / this.player.maxStamina);
      this.showStamina(_loc2_);
      this.caunter_mc.textStamina.showValue(this.player.stamina);
   }
}
