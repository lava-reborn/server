class lol.services.SpecSkillMessages
{
   var XMC;
   var attributes;
   var master;
   var rep_arr;
   var rep_later;
   var reputations;
   var skill_arr;
   var skill_later;
   var spec_arr;
   var spec_later;
   function SpecSkillMessages()
   {
      var _loc2_ = new lol.utils.Timeout(this,this.init,5000);
   }
   function init()
   {
      this.XMC = lol.server.XMLConnection.getInstance();
      this.master = lol.core.Master.getInstance();
      this.attributes = this.master.gamer.attributes;
      this.reputations = this.master.gamer.reputations;
      this.attributes.addEventListener(lol.core.player.PersAttributes.INCREASE_SKILL,this,this.increase_skill_func);
      this.attributes.addEventListener(lol.core.player.PersAttributes.INCREASE_LEVEL,this,this.increase_level_func);
      this.attributes.addEventListener(lol.core.player.PersAttributes.INCREASE_SPEC,this,this.increase_spec_func);
      this.attributes.addEventListener(lol.core.player.PersAttributes.INCREASE_SPEC_LEVEL,this,this.increase_spec_level_func);
      this.reputations.addEventListener(lol.core.player.Reputation.PersReputations.INCREASE_REPUTATION,this,this.increase_reputation);
      this.reputations.addEventListener(lol.core.player.Reputation.PersReputations.INCREASE_REP_LEVEL,this,this.increase_rep_level);
      this.master.addEventListener("changeWorld",this,this.changeWorld);
      this.XMC.addEventListener("lch",this,this.lch);
   }
   function kill()
   {
      this.attributes.removeEventListener(lol.core.player.PersAttributes.INCREASE_SKILL,this,this.increase_skill_func);
      this.attributes.removeEventListener(lol.core.player.PersAttributes.INCREASE_LEVEL,this,this.increase_level_func);
      this.attributes.removeEventListener(lol.core.player.PersAttributes.INCREASE_SPEC,this,this.increase_spec_func);
      this.attributes.removeEventListener(lol.core.player.PersAttributes.INCREASE_SPEC_LEVEL,this,this.increase_spec_level_func);
      this.master.removeEventListener("changeWorld",this,this.lch);
      this.XMC.removeEventListener("lch",this,this.lch);
   }
   function lch(obj)
   {
      var _loc2_ = obj.param.ws;
      this.changeWarState(_loc2_);
   }
   function changeWorld(obj)
   {
      this.changeWarState(0);
   }
   function warState()
   {
      return this.master.currentLocation.warStatus;
   }
   function changeWarState(st)
   {
      var _loc11_ = this.master.gamer.premium;
      var _loc8_;
      if(_loc11_ == 1)
      {
         _loc8_ = "вида на жительство: +";
      }
      else if(_loc11_ == 2)
      {
         _loc8_ = "гражданства: +";
      }
      var _loc2_;
      var _loc6_;
      var _loc3_;
      var _loc4_;
      var _loc5_;
      var _loc7_;
      if(st == 0)
      {
         for(var _loc9_ in this.skill_arr)
         {
            _loc2_ = this.skill_arr[_loc9_];
            _loc6_ = Number(_loc9_);
            _loc4_ = this.getSkillTitle(_loc6_) + ": +" + this.getRealAndBonus(_loc2_)[0] + " опыта";
            if(this.getRealAndBonus(_loc2_)[1])
            {
               _loc4_ += "\rБонус от " + _loc8_ + this.getRealAndBonus(_loc2_)[1] + " опыта";
               _loc3_ = lol.gpui.ServiceMessage["SKILL_" + _loc6_ + "_MESSAGE_PREMIUM"];
            }
            else
            {
               _loc3_ = lol.gpui.ServiceMessage["SKILL_" + _loc6_ + "_MESSAGE"];
            }
            this.showMessage(_loc4_,_loc3_);
         }
         if(this.skill_later)
         {
            this.showMessage(this.skill_later.str,lol.gpui.ServiceMessage["SKILL_" + this.skill_later.id + "_MESSAGE"]);
         }
         for(_loc9_ in this.spec_arr)
         {
            _loc2_ = this.spec_arr[_loc9_];
            if(_loc2_ != undefined)
            {
               _loc6_ = Number(_loc9_);
               _loc5_ = this.getSkillIDBySpecID(_loc6_);
               _loc4_ = this.master.gamer.attributes["spec" + _loc6_].title + ": +" + this.getRealAndBonus(_loc2_)[0] + " опыта";
               if(this.getRealAndBonus(_loc2_)[1])
               {
                  _loc4_ += "\rБонус от " + _loc8_ + this.getRealAndBonus(_loc2_)[1] + " опыта";
                  _loc3_ = lol.gpui.ServiceMessage["SKILL_" + _loc5_ + "_MESSAGE_PREMIUM"];
               }
               else
               {
                  _loc3_ = lol.gpui.ServiceMessage["SKILL_" + _loc5_ + "_MESSAGE"];
               }
               this.showMessage(_loc4_,_loc3_);
            }
         }
         if(this.spec_later)
         {
            this.showMessage(this.skill_later.str,lol.gpui.ServiceMessage["SKILL_" + this.skill_later.id + "_MESSAGE"]);
         }
         for(var _loc10_ in this.rep_arr)
         {
            _loc7_ = "Репутация " + _loc10_ + " повышена на: " + this.rep_arr[_loc9_];
            this.showMessage(_loc7_,lol.gpui.ServiceMessage.REPUTATION_MESSAGE);
         }
         if(this.rep_later)
         {
            this.showMessage(this.rep_later.report,lol.gpui.ServiceMessage.REPUTATION_MESSAGE);
         }
         delete this.skill_later;
         delete this.skill_later;
         delete this.skill_arr;
         delete this.spec_arr;
         delete this.rep_arr;
         delete this.rep_later;
      }
   }
   function increase_skill_func(obj)
   {
      var _loc2_ = obj.id;
      var _loc3_ = obj.value;
      var _loc4_ = this.getSkillTitle(_loc2_) + ": +" + this.getRealAndBonus(_loc3_)[0] + " опыта";
      var _loc5_;
      var _loc6_ = this.master.gamer.premium;
      var _loc7_;
      if(_loc6_ == 1)
      {
         _loc7_ = "вида на жительство: +";
      }
      else if(_loc6_ == 2)
      {
         _loc7_ = "гражданства: +";
      }
      if(this.getRealAndBonus(_loc3_)[1])
      {
         _loc4_ += "\rБонус от " + _loc7_ + this.getRealAndBonus(_loc3_)[1] + " опыта";
         _loc5_ = lol.gpui.ServiceMessage["SKILL_" + _loc2_ + "_MESSAGE_PREMIUM"];
      }
      else
      {
         _loc5_ = lol.gpui.ServiceMessage["SKILL_" + _loc2_ + "_MESSAGE"];
      }
      if(this.warState())
      {
         if(!this.skill_arr)
         {
            this.skill_arr = new Array();
         }
         this.skill_arr[_loc2_] = !this.skill_arr[_loc2_] ? _loc3_ : this.skill_arr[_loc2_] + _loc3_;
      }
      else
      {
         this.showMessage(_loc4_,_loc5_);
      }
   }
   function getRealAndBonus(value)
   {
      var _loc4_ = new Array();
      var _loc1_;
      var _loc2_;
      if(lol.core.Master.getInstance().gamer.premium)
      {
         if(lol.core.Master.getInstance().gamer.premium == 1)
         {
            _loc1_ = Math.round(value * lol.core.GConstatns.premium_xp_bonus_1 / (1 + lol.core.GConstatns.premium_xp_bonus_1));
         }
         else
         {
            _loc1_ = Math.round(value * lol.core.GConstatns.premium_xp_bonus_2 / (1 + lol.core.GConstatns.premium_xp_bonus_2));
         }
         _loc2_ = value - _loc1_;
         if(_loc2_ == 0)
         {
            _loc2_ = value;
            _loc1_ = 0;
         }
      }
      else
      {
         _loc2_ = value;
         _loc1_ = 0;
      }
      _loc4_[0] = _loc2_;
      _loc4_[1] = _loc1_;
      return _loc4_;
   }
   function increase_level_func(obj)
   {
      var _loc3_ = obj.id;
      var _loc2_ = obj.value;
      var _loc4_ = "Навык " + this.getSkillTitle(_loc3_) + " повышен до " + _loc2_;
      if(this.warState())
      {
         if(_loc2_ > 0)
         {
            this.skill_later = new Object();
            this.skill_later.id = _loc3_;
            this.skill_later.str = _loc4_;
         }
      }
      else if(_loc2_ > 0)
      {
         this.showMessage(_loc4_,lol.gpui.ServiceMessage["SKILL_" + _loc3_ + "_MESSAGE"]);
         lol.core.SceneShifter.newSkillLevelUpGameHelpMessage();
      }
   }
   function increase_spec_func(obj)
   {
      var _loc3_ = obj.id;
      var _loc2_ = obj.value;
      var _loc4_ = this.getSkillIDBySpecID(_loc3_);
      var _loc8_;
      var _loc5_ = this.master.gamer.attributes["spec" + _loc3_].title + ": +" + this.getRealAndBonus(_loc2_)[0] + " опыта";
      var _loc6_ = this.master.gamer.premium;
      var _loc7_;
      if(_loc6_ == 1)
      {
         _loc7_ = "вида на жительство: +";
      }
      else if(_loc6_ == 2)
      {
         _loc7_ = "гражданства: +";
      }
      if(this.getRealAndBonus(_loc2_)[1])
      {
         _loc5_ += "\rБонус от " + _loc7_ + this.getRealAndBonus(_loc2_)[1] + " опыта";
         _loc8_ = lol.gpui.ServiceMessage["SKILL_" + _loc4_ + "_MESSAGE_PREMIUM"];
      }
      else
      {
         _loc8_ = lol.gpui.ServiceMessage["SKILL_" + _loc4_ + "_MESSAGE"];
      }
      if(this.warState())
      {
         if(!this.spec_arr)
         {
            this.spec_arr = new Array();
         }
         this.spec_arr[_loc3_] = !this.spec_arr[_loc3_] ? _loc2_ : this.spec_arr[_loc3_] + _loc2_;
      }
      else
      {
         this.showMessage(_loc5_,lol.gpui.ServiceMessage["SKILL_" + _loc4_ + "_MESSAGE"]);
      }
   }
   function increase_spec_level_func(obj)
   {
      var _loc2_ = obj.id;
      var _loc4_ = obj.value;
      var _loc3_ = "Специализация " + this.master.gamer.attributes["spec" + _loc2_].title + " повышена до " + _loc4_;
      if(this.warState())
      {
         this.skill_later = new Object();
         this.skill_later.id = _loc2_;
         this.skill_later.str = _loc3_;
      }
      else
      {
         this.showMessage(_loc3_,lol.gpui.ServiceMessage["SKILL_" + _loc2_ + "_MESSAGE"]);
      }
   }
   function showMessage(str, type)
   {
      lol.core.SceneShifter.newServiceMessage(str,type);
   }
   function getSkillIDBySpecID(id)
   {
      var _loc1_;
      if(id >= 12)
      {
         _loc1_ = 4;
      }
      else if(id >= 10)
      {
         _loc1_ = 3;
      }
      else if(id >= 8)
      {
         _loc1_ = 2;
      }
      else if(id >= 2)
      {
         _loc1_ = 1;
      }
      else
      {
         _loc1_ = 0;
      }
      return _loc1_;
   }
   function getSkillTitle(id)
   {
      switch(id)
      {
         case 0:
            return "Ближний бой";
         case 1:
            return "Стрельба";
         case 2:
            return "Медицина";
         case 3:
            return "Промышленность";
         case 4:
            return "Производство";
         default:
            return;
      }
   }
   function increase_reputation(obj)
   {
      var _loc2_ = obj.value;
      var _loc3_ = obj.title;
      var _loc4_ = _loc3_ + " повышен на: " + _loc2_;
      if(this.warState())
      {
         if(!this.rep_arr)
         {
            this.rep_arr = new Array();
         }
         this.rep_arr[_loc3_] = _loc2_;
      }
      else
      {
         this.showMessage(_loc4_,lol.gpui.ServiceMessage.REPUTATION_MESSAGE);
      }
   }
   function increase_rep_level(obj)
   {
      var _loc2_ = obj.value;
      var _loc4_ = obj.title;
      var _loc3_ = _loc4_ + " повышен до уровня: " + _loc2_;
      if(this.warState())
      {
         if(_loc2_ > 0)
         {
            this.rep_later = new Object();
            this.rep_later.value = _loc2_;
            this.rep_later.report = _loc3_;
         }
      }
      else if(_loc2_ > 0)
      {
         this.showMessage(_loc3_,lol.gpui.ServiceMessage.REPUTATION_MESSAGE);
      }
   }
}
