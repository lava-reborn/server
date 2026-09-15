class lol.core.location.CharInfo extends MovieClip
{
   var NY_mc;
   var __relation;
   var ac;
   var addSteckArr;
   var c;
   var count;
   var curHealth;
   var curStamina;
   var hBar;
   var health;
   var highLightMark;
   var id;
   var infoShadow_txt;
   var info_txt;
   var l;
   var mobLevel_mc;
   var npcMark;
   var onEnterFrame;
   var pause;
   var phraseTextField;
   var player;
   var premiumStar_mc;
   var prepare_txt;
   var removePhraseInterval;
   var repSign_mc;
   var sBar;
   var sh_btn;
   var stamina;
   var startTimer;
   var tf;
   var timer;
   var allow = false;
   var timerFlag = false;
   static var firstGameID = undefined;
   var n = 0;
   var nn = 10;
   function CharInfo()
   {
      super();
      var _loc3_ = new lol.utils.Timeout(this,this.allowFunc,1000);
      this.info_txt.html = true;
      this.tf = new TextFormat();
      this.tf.bold = true;
   }
   function allowFunc()
   {
      this.allow = true;
      if(lol.core.Master.getInstance().gamer.attributes.getLevel() == 0)
      {
         this.sh_btn.addEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.addHint);
      }
   }
   function addHint()
   {
      if(lol.core.Master.getInstance().gamer.attributes.getLevel() == 0)
      {
         lol.core.SceneShifter.hintManager.addHint(lol.gpui.HintManager.STAMINA_HEALTH_BAR,this.sh_btn);
      }
   }
   function setNick(_id)
   {
      this.id = _id;
      this.player = lol.core.Master.getInstance().getPlayer(this.id);
      var _loc3_ = this.player.playerInfo;
      if(_loc3_.name)
      {
         this.userInfoUpdate();
      }
      this.player.addEventListener(lol.events.PlayerEvent.UPDATE_INFO,this,this.userInfoUpdate);
      this.player.addEventListener(lol.events.PlayerEvent.UPDATE_STATE,this,this.updateState);
      this.health = this.player.attributes.health;
      this.stamina = this.player.attributes.stamina;
      if(this.player.premium)
      {
         this.premiumStar_mc.gotoAndStop(this.player.premium + 1);
      }
      var _loc2_;
      if(this.player instanceof lol.core.player.Mob)
      {
         lol.core.Master.getInstance().gamer.attributes.addEventListener(lol.core.player.PersAttributes.INCREASE_LEVEL,this,this.increaseGamerLevel);
      }
      else if(this.player instanceof lol.core.player.NPC)
      {
         this.hBar._visible = false;
         this.sBar._visible = false;
      }
      else
      {
         _loc2_ = this.player.reputations;
         if(_loc2_)
         {
            this.addReputationSign();
         }
      }
      lol.core.clans.ClanInspector.getInstance().addEventListener(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE,this,this.clanNameUpdate);
      lol.core.clans.ClanInspector.getInstance().addEventListener(lol.core.clans.ClanEvent.OTHER_CLAN_MEMBER_ARRIVED,this,this.clanNameUpdate);
      lol.core.clans.ClanInspector.getInstance().addEventListener(lol.core.clans.ClanEvent.CLAN_LEAVE_SUCCES,this,this.clanNameUpdate_pause);
      lol.core.clans.ClanInspector.getInstance().addEventListener(lol.core.clans.ClanEvent.KICKED_FROM_CLAN,this,this.clanNameUpdate_pause);
      lol.core.clans.ClanInspector.getInstance().addEventListener(lol.core.clans.ClanEvent.CLAN_INVITE_ANSWER_SUCCES,this,this.clanNameUpdate);
      lol.core.clans.ClanInspector.getInstance().addEventListener(lol.core.clans.ClanEvent.NEW_CLAN_MEMBER_ADDED,this,this.clanNameUpdate);
      lol.core.party.PartyManager.getInstance().addEventListener(lol.core.party.PartyEvent.JOIN_TO_PARTY,this,this.partyColorUpdate);
      lol.core.party.PartyManager.getInstance().addEventListener(lol.core.party.PartyEvent.DISBAND_PARTY,this,this.partyColorUpdate);
      lol.core.party.PartyManager.getInstance().addEventListener(lol.core.party.PartyEvent.KICKED_FROM_PARTY,this,this.partyColorUpdate);
      lol.core.party.PartyManager.getInstance().addEventListener(lol.core.party.PartyEvent.LEAVE_PARTY,this,this.partyColorUpdate);
      lol.core.party.PartyManager.getInstance().addEventListener(lol.core.party.PartyEvent.PARTY_LIST_REFRESH,this,this.partyColorUpdate);
      this.player.equipment.addEventListener("addItem",this,this.addItem);
      this.player.equipment.addEventListener("removeItem",this,this.removeItem);
      this.player.addEventListener(lol.events.PlayerEvent.PREPARE,this,this.prepare);
      this.player.effects.addEventListener(lol.events.PlayerEvent.NEW_DEBUFF_EFFECT,this,this.NewDebuffEffect);
      var _loc4_ = new Object();
      _loc4_.id = "head";
      this.addItem({slot:_loc4_});
      this.prepare();
      this.checkColor();
   }
   function kill()
   {
      lol.core.Master.getInstance().gamer.attributes.removeEventListener(lol.core.player.PersAttributes.INCREASE_LEVEL,this,this.increaseGamerLevel);
      lol.core.clans.ClanInspector.getInstance().removeEventListener(lol.core.clans.ClanEvent.CLAN_LIST_UPDATE,this,this.clanNameUpdate);
      lol.core.clans.ClanInspector.getInstance().removeEventListener(lol.core.clans.ClanEvent.OTHER_CLAN_MEMBER_ARRIVED,this,this.clanNameUpdate);
      lol.core.clans.ClanInspector.getInstance().removeEventListener(lol.core.clans.ClanEvent.CLAN_LEAVE_SUCCES,this,this.clanNameUpdate_pause);
      lol.core.clans.ClanInspector.getInstance().removeEventListener(lol.core.clans.ClanEvent.KICKED_FROM_CLAN,this,this.clanNameUpdate_pause);
      lol.core.clans.ClanInspector.getInstance().removeEventListener(lol.core.clans.ClanEvent.CLAN_INVITE_ANSWER_SUCCES,this,this.clanNameUpdate);
      lol.core.clans.ClanInspector.getInstance().removeEventListener(lol.core.clans.ClanEvent.NEW_CLAN_MEMBER_ADDED,this,this.clanNameUpdate);
      lol.core.party.PartyManager.getInstance().removeEventListener(lol.core.party.PartyEvent.JOIN_TO_PARTY,this,this.partyColorUpdate_pause);
      lol.core.party.PartyManager.getInstance().removeEventListener(lol.core.party.PartyEvent.DISBAND_PARTY,this,this.partyColorUpdate_pause);
      lol.core.party.PartyManager.getInstance().removeEventListener(lol.core.party.PartyEvent.KICKED_FROM_PARTY,this,this.partyColorUpdate_pause);
      lol.core.party.PartyManager.getInstance().removeEventListener(lol.core.party.PartyEvent.LEAVE_PARTY,this,this.partyColorUpdate_pause);
      lol.core.party.PartyManager.getInstance().removeEventListener(lol.core.party.PartyEvent.PARTY_LIST_REFRESH,this,this.partyColorUpdate_pause);
      lol.core.SceneShifter.hintManager.removeHint(lol.gpui.HintManager.STAMINA_HEALTH_BAR,this.sh_btn);
      this.sh_btn.removeEventListener(lol.gpui.controls.GPUIButton.ROLL_OVER_EVENT,this,this.addHint);
      this.player.equipment.removeEventListener("addItem",this,this.addItem);
      this.player.equipment.removeEventListener("removeItem",this,this.removeItem);
      this.player.removeEventListener(lol.events.PlayerEvent.UPDATE_STATE,this,this.updateState);
      this.player.removeEventListener(lol.events.PlayerEvent.PREPARE,this,this.prepare);
      this.player.effects.removeEventListener(lol.events.PlayerEvent.NEW_DEBUFF_EFFECT,this,this.NewDebuffEffect);
   }
   function NewDebuffEffect(eventObj)
   {
      if(eventObj.debuff_msg != undefined && eventObj.mob_id != undefined)
      {
         this.showPhrase(eventObj.debuff_msg,16711680);
      }
   }
   function prepare(obj)
   {
      var _loc2_ = this.player.prepare;
      if(_loc2_)
      {
         if(!this.timerFlag)
         {
            this.timerFlag = true;
            this.count = _loc2_;
            this.startTimer = getTimer();
            this.timer = setInterval(this,"prepareTimer",100,_loc2_);
         }
      }
      else
      {
         this.timerFlag = false;
         clearInterval(this.timer);
         this.prepare_txt.text = "";
      }
   }
   function prepareTimer(time)
   {
      this.count = Math.floor((getTimer() - this.startTimer) / 1000);
      if(this.count == time)
      {
         this.timerFlag = false;
         clearInterval(this.timer);
         this.prepare_txt.text = "";
      }
      else
      {
         this.prepare_txt.text = String(time - this.count);
         this.prepare_txt.setTextFormat(this.tf);
      }
   }
   function clanNameUpdate_pause()
   {
      var _loc2_ = new lol.utils.Timeout(this,this.clanNameUpdate,1000);
   }
   function clanNameUpdate()
   {
      var _loc2_ = lol.core.Master.getInstance().getPlayer(this.id);
      var _loc3_ = _loc2_.playerInfo.name;
      var _loc5_ = _loc2_.attributes.level;
      if(_loc2_ instanceof lol.core.player.Player && _loc5_ != undefined && !isNaN(_loc5_))
      {
         _loc3_ = "[" + String(_loc5_) + "] " + _loc3_;
      }
      var _loc4_ = _loc2_.clanMemberInfo.clanInfo.clanName;
      var _loc7_ = _loc2_.clanMemberInfo.clanReg;
      var _loc6_;
      if(_loc3_)
      {
         _loc6_ = lol.utils.ParseString.replaceAll(_loc3_,"\\","");
         if(_loc4_ != "" && _loc4_ != undefined && _loc7_ != 0)
         {
            this.info_txt.htmlText = _loc6_ + "\r&lt;" + _loc4_ + "&gt;";
         }
         else
         {
            this.info_txt.htmlText = _loc6_;
         }
      }
      this.info_txt._y = !this.hBar._visible ? Math.round(this.sBar._y - this.info_txt.textHeight) : Math.round(this.hBar._y - this.info_txt.textHeight - 5);
      this.infoShadow_txt._y = Math.round(this.info_txt._y + 1);
      this.addLevelMc(_loc2_);
      var _loc8_ = new Object();
      _loc8_.id = "head";
      this.addItem({slot:_loc8_});
      this.checkColor();
   }
   function partyColorUpdate_pause()
   {
      var _loc2_ = new lol.utils.Timeout(this,this.partyColorUpdate,1000);
   }
   function partyColorUpdate()
   {
      this.checkColor();
   }
   function userInfoUpdate(obj)
   {
      var _loc2_ = lol.core.Master.getInstance().getPlayer(this.id);
      var _loc3_ = _loc2_.playerInfo.name;
      var _loc5_ = _loc2_.attributes.level;
      if(_loc2_ instanceof lol.core.player.Player && _loc5_ != undefined && !isNaN(_loc5_))
      {
         _loc3_ = "[" + String(_loc5_) + "] " + _loc3_;
      }
      var _loc7_ = 100 * _loc2_.health / _loc2_.maxHealth;
      var _loc8_ = 100 * _loc2_.stamina / _loc2_.maxStamina;
      this.health = _loc2_.attributes.health;
      this.stamina = _loc2_.attributes.stamina;
      this.showHealth(_loc7_,_loc2_.health);
      this.showStamina(_loc8_,_loc2_.stamina);
      var _loc4_ = lol.core.Master.getInstance().getPlayer(this.id).clanMemberInfo.clanInfo.clanName;
      var _loc10_ = lol.core.Master.getInstance().getPlayer(this.id).clanMemberInfo.clanReg;
      var _loc6_;
      if(_loc3_)
      {
         _loc6_ = lol.utils.ParseString.replaceAll(_loc3_,"\\","");
         if(_loc4_ != "" && _loc4_ != undefined && _loc10_ != 0)
         {
            this.info_txt.htmlText = _loc6_ + "\r&lt;" + _loc4_ + "&gt;";
         }
         else
         {
            this.info_txt.htmlText = _loc6_;
         }
      }
      else
      {
         this.info_txt.htmlText = String(this.id);
      }
      if(_loc2_.premium)
      {
         this.premiumStar_mc.gotoAndStop(_loc2_.premium + 1);
      }
      this.info_txt._y = !this.hBar._visible ? Math.round(this.sBar._y - this.info_txt.textHeight) : Math.round(this.hBar._y - this.info_txt.textHeight - 5);
      this.infoShadow_txt._y = Math.round(this.info_txt._y + 1);
      var _loc11_;
      var _loc9_;
      if(_loc2_ instanceof lol.core.player.NPC)
      {
         _loc11_ = lol.core.player.NPC(_loc2_);
         lol.core.quests.QuestInspector.getInstance().addEventListener("update",this,this.setNPCMark);
         this.setNPCMark();
      }
      else if(_loc2_ instanceof lol.core.player.Player)
      {
         _loc9_ = lol.core.player.Player(_loc2_).highLight;
         this.addHighLightMark(_loc9_);
      }
      if(_loc2_ instanceof lol.core.player.Mob)
      {
         this.addLevelMc(_loc2_);
      }
      else
      {
         this.addReputationSign();
      }
      this.checkColor();
   }
   function increaseGamerLevel()
   {
      var _loc2_ = lol.core.Master.getInstance().getPlayer(this.id);
      this.addLevelMc(_loc2_);
   }
   function addLevelMc(_mob)
   {
      var _loc3_;
      var _loc4_;
      var _loc2_;
      if(_mob instanceof lol.core.player.Mob)
      {
         _loc3_ = lol.core.Master.getInstance().gamer.attributes.level;
         _loc4_ = _mob.attributes.level;
         _loc2_ = lol.core.player.PersAttributes.compareLevels(_loc4_,_loc3_);
         this.mobLevel_mc.removeMovieClip();
         this.mobLevel_mc = this.attachMovie("mobLevel_mc","mobLevel_mc",this.getNextHighestDepth());
         this.mobLevel_mc.gotoAndStop(_loc2_ + 5);
         this.mobLevel_mc._y = this.info_txt._y - 1;
         this.mobLevel_mc._x = Math.round(this.info_txt.textWidth / 2) + 4;
      }
   }
   function addReputationSign()
   {
      var _loc3_ = lol.core.Master.getInstance().getPlayer(this.id);
      var _loc2_;
      var _loc4_;
      if(_loc3_)
      {
         this.repSign_mc.removeMovieClip();
         _loc2_ = _loc3_.reputations._reputations[0].value_bonus;
         if(_loc2_ != undefined)
         {
            _loc4_ = Number(_loc2_) + 1;
            this.repSign_mc = this.attachMovie("repLevel_icon","repLevel_icon",this.getNextHighestDepth());
            this.repSign_mc.gotoAndStop(_loc4_);
            this.repSign_mc._y = this.hBar._y - 4;
            this.repSign_mc._x = this.hBar._x + this.hBar._width + 1;
         }
      }
   }
   function addItem(obj)
   {
      var _loc4_ = obj.slot;
      var _loc2_;
      var _loc3_;
      if(_loc4_.id == "head")
      {
         _loc2_ = this.player.equipment.head.item;
         if(!_loc2_.getProp("name"))
         {
            _loc2_.addEventListener("itemUpdate",this,this.itemUpdate);
         }
         _loc3_ = _loc2_.getProp("sub_name");
         if(_loc3_ != undefined)
         {
            this.addNewYearMc(_loc3_);
         }
         else
         {
            this.addNewYearMc(0);
         }
      }
   }
   function itemUpdate(obj)
   {
      var _loc3_ = this.player.equipment.head.item;
      obj.target.removeEventListener("itemUpdate",this,this.itemUpdate);
      var _loc2_ = _loc3_.getProp("sub_name");
      if(_loc2_ != undefined)
      {
         this.addNewYearMc(_loc2_);
      }
      else
      {
         this.addNewYearMc(0);
      }
   }
   function removeItem(obj)
   {
      var _loc2_ = obj.slot;
      if(_loc2_.id == "head")
      {
         this.addNewYearMc(0);
      }
   }
   function addNewYearMc(n)
   {
      this.NY_mc.removeMovieClip();
      if(n != 0)
      {
         this.NY_mc = this.attachMovie("NY_mc","NY_mc",this.getNextHighestDepth());
      }
      this.NY_mc.gotoAndStop(n);
      this.NY_mc._y = this.info_txt._y;
   }
   function setNPCMark(obj)
   {
      var _loc4_ = lol.core.player.NPC(lol.core.Master.getInstance().getPlayer(this.id));
      var _loc8_ = _loc4_.playerInfo.name;
      this.npcMark.removeMovieClip();
      var _loc7_;
      var _loc2_;
      var _loc3_;
      var _loc6_;
      if(_loc4_.hasAvailableQuests())
      {
         _loc7_ = this.getNextHighestDepth();
         this.npcMark = this.attachMovie("NPCmark","NPCmark",_loc7_);
         this.npcMark._y = this.info_txt._y;
         _loc2_ = lol.core.quests.QuestInspector.getInstance().getTQs(_loc4_);
         if(_loc2_.length > 0)
         {
            _loc3_ = false;
            for(var _loc5_ in _loc2_)
            {
               if(_loc2_[_loc5_].complete)
               {
                  _loc3_ = true;
                  break;
               }
            }
            if(_loc3_)
            {
               this.npcMark.gotoAndStop(2);
            }
            else
            {
               this.npcMark.gotoAndStop(3);
            }
         }
         else
         {
            _loc6_ = _loc4_.getHighPriorityQuestType();
            if(_loc6_ > 0)
            {
               this.npcMark.gotoAndStop(3 + _loc6_);
            }
            else if(lol.core.SceneShifter.firstGame == true)
            {
               if(lol.core.location.CharInfo.firstGameID == undefined)
               {
                  lol.core.location.CharInfo.firstGameID = this.id;
                  this.npcMark.gotoAndStop(16);
               }
               else if(lol.core.location.CharInfo.firstGameID == this.id)
               {
                  this.npcMark.gotoAndStop(16);
               }
            }
            else
            {
               this.npcMark.gotoAndStop(0);
            }
         }
         this.npcMark.onRollOver = mx.utils.Delegate.create(this,this.npcMarkActivate);
         this.npcMark.onRollOut = mx.utils.Delegate.create(this,this.npcMarkDeactivate);
         this.npcMark.onReleaseOutside = mx.utils.Delegate.create(this,this.npcMarkDeactivate);
         this.npcMark.onPress = mx.utils.Delegate.create(this,this.gotoNPC);
      }
   }
   function npcMarkActivate()
   {
      var _loc2_ = new flash.filters.GlowFilter(16777215,90,8,8,1,1,false);
      this.npcMark.filters = [_loc2_];
   }
   function npcMarkDeactivate()
   {
      this.npcMark.filters = [];
   }
   function gotoNPC()
   {
      lol.core.Master.getInstance().gamer.gotoWalker(this.id,"contact");
   }
   function addHighLightMark(hl)
   {
      this.highLightMark.removeMovieClip();
      var _loc2_;
      if(hl)
      {
         _loc2_ = this.getNextHighestDepth();
         this.highLightMark = this.attachMovie("hlMark","highLightMark",_loc2_);
         this.highLightMark._y = this.info_txt._y;
      }
   }
   function checkColor()
   {
      var _loc5_ = lol.core.Master.getInstance().getPlayer(this.id);
      var _loc10_;
      var _loc7_;
      var _loc4_;
      var _loc9_;
      var _loc8_;
      var _loc3_;
      var _loc11_;
      var _loc2_;
      if(this.id == lol.core.player.Gamer.ID)
      {
         this.relation = "gamer";
      }
      else if(_loc5_ instanceof lol.core.player.NPC || _loc5_ instanceof lol.core.player.Mob)
      {
         _loc10_ = _loc5_.playerInfo.ally;
         if(_loc10_)
         {
            this.relation = "friend";
         }
         else
         {
            this.relation = "neutral";
         }
      }
      else if(_loc5_ instanceof lol.core.player.Player)
      {
         _loc7_ = lol.core.Master.getInstance().gamer.partyManager;
         if(_loc7_ && _loc7_.inParty(_loc5_.id))
         {
            this.relation = "friend";
         }
         else
         {
            this.relation = "neutral";
         }
         _loc4_ = _loc5_.clanMemberInfo.clanReg;
         _loc9_ = lol.core.Master.getInstance().gamer.clanMemberInfo.clanReg;
         if(_loc4_ != 0 && _loc4_ == _loc9_)
         {
            this.relation = "friend";
         }
         else if(_loc4_ != 0)
         {
            this.relation = "neutral";
            _loc8_ = lol.core.Master.getInstance().gamer.clanMemberInfo.clanInfo;
            if(_loc8_ != undefined)
            {
               _loc3_ = _loc8_.standingArray;
               if(_loc3_ != undefined)
               {
                  _loc11_ = lol.core.Master.getInstance().gamer.clanMemberInfo.clanInfo.clanName;
                  for(var _loc6_ in _loc3_)
                  {
                     _loc2_ = _loc3_[_loc6_];
                     if(_loc4_ == _loc2_.data)
                     {
                        switch(_loc2_.stat)
                        {
                           case 0:
                              this.relation = "neutral";
                              break;
                           case 1:
                              this.relation = "friend";
                              break;
                           case -1:
                              this.relation = "enemy";
                              break;
                           default:
                              this.relation = "neutral";
                        }
                     }
                  }
               }
            }
            else
            {
               trace("clanInfo = undefined");
            }
         }
      }
   }
   function set relation(rel)
   {
      var _loc2_;
      switch(rel)
      {
         case "enemy":
            _loc2_ = 16711680;
            break;
         case "friend":
            _loc2_ = 11992904;
            break;
         case "neutral":
            _loc2_ = 16776960;
            break;
         case "gamer":
            _loc2_ = 16777215;
            break;
         default:
            _loc2_ = 16776960;
      }
      this.__relation = rel;
      var _loc3_ = new TextFormat();
      _loc3_.color = _loc2_;
      this.info_txt.setTextFormat(_loc3_);
   }
   function updateState()
   {
      this.health = this.player.attributes.health;
      this.stamina = this.player.attributes.stamina;
      if(this.curHealth != this.health && this.curHealth != undefined)
      {
         this.showDamage(this.health - this.curHealth,"health",this.player.critDamage);
      }
      if(this.curStamina != this.stamina && this.curStamina != undefined)
      {
         this.showDamage(this.stamina - this.curStamina,"stamina",this.player.critDamage);
      }
      this.curHealth = this.health;
      this.curStamina = this.stamina;
   }
   function showDamage(num, type, crit)
   {
      var _loc11_;
      var _loc6_;
      var _loc12_;
      if(type == "health")
      {
         _loc6_ = 0;
      }
      else if(type == "stamina")
      {
         _loc6_ = 10;
      }
      var _loc2_;
      var _loc4_;
      var _loc3_;
      if(this.allow)
      {
         _loc2_ = num;
         if(type == "health")
         {
            if(_loc2_ > 0)
            {
               _loc4_ = "healthPlusFont";
               lol.services.GameEvents.addEvent(lol.services.GameEvents.REGENERATE_HEALTH,{nickname:this.player.playerInfo.name,value:_loc2_});
            }
            else
            {
               _loc4_ = "healthMinusFont";
            }
         }
         else if(type == "stamina")
         {
            if(_loc2_ > 0)
            {
               lol.services.GameEvents.addEvent(lol.services.GameEvents.REGENERATE_STAMINA,{nickname:this.player.playerInfo.name,value:_loc2_});
            }
            _loc4_ = "staminaFont";
         }
         if(_loc2_ > 0)
         {
            _loc3_ = "+" + _loc2_;
         }
         else
         {
            _loc3_ = _loc2_;
         }
         if(crit && _loc2_ < 0 && type == "health")
         {
            _loc3_ = "c" + _loc3_;
         }
         this.addCount(_loc4_,_loc3_);
      }
      return _loc2_;
   }
   function addCount(attachText, dmg)
   {
      if(!this.addSteckArr)
      {
         this.addSteckArr = new Array();
      }
      this.addSteckArr.push({attachText:attachText,dmg:dmg});
      this.onEnterFrame = this._addCount;
   }
   function _addCount()
   {
      var _loc3_;
      var _loc2_;
      if(this.n == this.nn)
      {
         _loc3_ = this.getNextHighestDepth();
         _loc2_ = this.attachMovie("textCharCreate","dm" + _loc3_,_loc3_);
         _loc2_._visible = false;
         _loc2_.alignText = "center";
         _loc2_.letterSpace = -1;
         _loc2_.attachText = this.addSteckArr[0].attachText;
         _loc2_.showValue(this.addSteckArr[0].dmg);
         this.animationNum(_loc2_,35);
         this.addSteckArr.shift();
         this.n = 0;
      }
      else
      {
         this.n = this.n + 1;
      }
      if(this.addSteckArr.length == 0)
      {
         delete this.onEnterFrame;
      }
   }
   function showHealth(hpercent, h)
   {
      this.hBar.hbar._xscale = hpercent;
   }
   function showStamina(spercent, s)
   {
      this.sBar.sbar._xscale = spercent;
   }
   function animationNum(d, type)
   {
      d.c = 0;
      d.l = type;
      d.pause = 0;
      d.onEnterFrame = function()
      {
         this.c = this.c + 1;
         if(this.c > this.pause)
         {
            if(!this._visible)
            {
               this._visible = true;
            }
            if(this.c > this.l + this.pause)
            {
               if(this.c > this.l + 10)
               {
                  delete this.onEnterFrame;
                  this.removeMovieClip();
               }
               else
               {
                  this._alpha -= 10;
               }
            }
            else
            {
               this._y = this._y - 1;
            }
         }
      };
   }
   function autoAim(f)
   {
      this.ac.removeMovieClip();
      if(f)
      {
         this.ac = this.attachMovie("fireAutoAim","ac",this.getNextHighestDepth());
      }
   }
   function showPhrase(phrase, color)
   {
      clearInterval(this.removePhraseInterval);
      this.phraseTextField.removeTextField();
      this.phraseTextField = this.createTextField("phraseTextField",this.getNextHighestDepth(),0,0,200,20);
      this.phraseTextField.autoSize = true;
      this.phraseTextField.multiline = true;
      this.phraseTextField.wordWrap = true;
      var _loc2_ = new TextFormat();
      if(color != undefined)
      {
         _loc2_.color = color;
      }
      else
      {
         _loc2_.color = 16777215;
      }
      _loc2_.align = "center";
      _loc2_.font = "Microsoft Sans Serif";
      _loc2_.bold = true;
      var _loc4_ = new flash.filters.GlowFilter(0,1,2,2,255,1,false,false);
      this.phraseTextField.filters = [_loc4_];
      var _loc3_ = phrase.length <= 20 ? phrase : phrase.substr(0,20) + "...";
      this.phraseTextField.text = _loc3_;
      this.phraseTextField.setTextFormat(_loc2_);
      this.phraseTextField._x = (- this.phraseTextField._width) / 2;
      this.phraseTextField._y = - this.phraseTextField._height - 10;
      this.removePhraseInterval = setInterval(this,"removePhrase",2000);
   }
   function removePhrase()
   {
      clearInterval(this.removePhraseInterval);
      this.phraseTextField.removeTextField();
   }
}
