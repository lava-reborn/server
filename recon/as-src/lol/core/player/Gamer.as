class lol.core.player.Gamer extends lol.core.player.Player
{
   var XMC;
   var acManager;
   var apManager;
   var attributes;
   var auction;
   var bank;
   var bankAccount;
   var barter;
   var contactManager;
   var dispatchEvent;
   var equipment;
   var id;
   var itemActivator;
   var loot;
   var partyManager;
   var playerInfo;
   var rent;
   var servicer;
   var spt;
   var spt_int;
   var ssMessages;
   var stuff_func;
   var stuff_param;
   var trade;
   var training;
   var upgrade;
   var walker;
   static var staticID = "Gamer";
   static var ID = 0;
   function Gamer(ID)
   {
      super(ID);
      this.XMC.addEventListener("ss_create",this);
      this.XMC.addEventListener("rp_info",this.attributes);
      this.XMC.addEventListener("ss_obj_status",this.equipment);
      this.apManager = new lol.core.player.APManager();
      this.ssMessages = new lol.services.SpecSkillMessages();
      this.itemActivator = new lol.core.objects.ItemActivator(this);
      this.contactManager = new lol.core.player.ContactManager();
      this.bankAccount = new lol.core.player.BankAccount();
      this.acManager = new lol.services.AutoCommandManager();
      this.partyManager = lol.core.party.PartyManager.getInstance();
   }
   function requestInfo()
   {
      super.requestInfo();
   }
   function requestAttributes()
   {
      this.attributes.requestAttributes();
   }
   function userInfo(obj)
   {
      var _loc4_ = obj.param.afro;
      var _loc5_ = obj.param.gold;
      this.attributes.afro = _loc4_;
      this.attributes.gold = _loc5_;
      this.playerInfo.transport = lol.core.transport.TransportFactory.create(obj.param.tr);
      this.playerInfo.transRentTime = obj.param.tr_hours;
      super.userInfo(obj);
   }
   function setMoney(afro, gold)
   {
      this.attributes.afro = afro;
      this.attributes.gold = gold;
      this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_INFO,this));
   }
   function gotoLoot(pos)
   {
      var _loc5_ = this.walker.numPos;
      var _loc4_;
      var _loc3_;
      var _loc6_;
      if(_loc5_ == pos)
      {
         this.createLoot(pos);
      }
      else
      {
         this.stuff_param = pos;
         this.stuff_func = this.createLoot;
         _loc4_ = lol.core.Master.getInstance();
         _loc3_ = _loc4_.currentLocation;
         _loc6_ = _loc3_.getCellFromNumber(pos);
         this.walker.addEventListener("finishMove",this);
         _loc3_.movePlayer(_loc6_);
      }
   }
   function createLoot(pos)
   {
      if(this.walker.numPos == pos)
      {
         this.walker.removeEventListener("finishMove",this);
         this.loot = new lol.core.player.Loot();
         this.loot.createSession(pos);
      }
   }
   function finishMove(obj)
   {
      this.stuff_func.apply(this,[this.stuff_param]);
   }
   function sendInviteToParty(guest_id)
   {
      var _loc2_ = new lol.server.mess.CSM_P_OP(lol.core.party.PartyManager.PARTY_SEND_INVITE_PLAYER,guest_id);
      if(this.XMC.Send(_loc2_))
      {
         lol.server.XMLCCallStack.addCall("cmdAck",this,this.invitePlayer,guest_id);
      }
   }
   function invitePlayer(obj)
   {
      var _loc2_;
      if(obj.param.res == 31)
      {
         _loc2_ = lol.core.SceneShifter.openNewWindow("alert","center");
         _loc2_.content.write("Игрок не может быть приглашен в ваш отряд в данный момент");
      }
      if(obj.param.res == 0)
      {
         this.partyManager.setLeader(this.id);
      }
   }
   function gotoWalker(id, action)
   {
      var _loc7_ = this.walker.numPos;
      var _loc6_ = lol.core.Master.getInstance();
      var _loc2_ = _loc6_.currentLocation;
      var _loc5_ = _loc2_.getCellFromNumber(_loc7_);
      var _loc8_ = _loc2_.getWalker(id);
      var _loc4_ = _loc2_.getCellFromNumber(_loc8_.numPos);
      var _loc9_;
      if(_loc5_ == _loc4_ || _loc2_.isSiblings(_loc5_,_loc4_))
      {
         if(action == "contact")
         {
            this.proposeContact({id:id,targetCell:_loc4_});
         }
         else if(action == "heal")
         {
            this.heal({id:id,targetCell:_loc4_});
         }
         else if(action == "strike")
         {
            this.strike({id:id,targetCell:_loc4_});
         }
      }
      else
      {
         this.stuff_param = {id:id,targetCell:_loc4_};
         if(action == "contact")
         {
            this.stuff_func = this.proposeContact;
         }
         else if(action == "heal")
         {
            this.stuff_func = this.heal;
         }
         else if(action == "strike")
         {
            this.stuff_func = this.strike;
         }
         this.walker.addEventListener("finishMove",this);
         _loc9_ = !(!_loc2_.locInfo.battle && !_loc4_.alwaysBusy) ? 0 : 1;
         _loc2_.movePlayer(_loc4_,_loc9_);
      }
   }
   function proposeContact(obj)
   {
      var _loc5_ = lol.core.Master.getInstance();
      var _loc8_ = _loc5_.currentLocation;
      var _loc7_ = _loc8_.getCellFromNumber(this.walker.numPos);
      var _loc6_ = obj.targetCell;
      var _loc2_ = _loc5_.getPlayer(obj.id);
      var _loc4_;
      var _loc11_;
      var _loc10_;
      var _loc9_;
      if(_loc7_ == _loc6_ || _loc8_.isSiblings(_loc7_,_loc6_))
      {
         this.walker.removeEventListener("finishMove",this);
         if(_loc2_ instanceof lol.core.player.NPC)
         {
            if(lol.core.player.NPC(_loc2_).hasAvailableQuests())
            {
               lol.core.quests.QuestInspector.getInstance().setQuestNPC(lol.core.player.NPC(_loc2_));
            }
            else
            {
               lol.core.quests.QuestInspector.getInstance().setQuestNPC(null);
            }
            this.servicer = lol.core.player.NPC(_loc2_);
         }
         else
         {
            this.servicer = null;
         }
         if(_loc2_ instanceof lol.core.player.Player)
         {
            if(!this.barter)
            {
               this.barter = new lol.core.player.Barter();
               this.barter.ss_propose(obj.id);
            }
         }
         else if(_loc2_ instanceof lol.core.player.Trader && lol.core.player.NPC(_loc2_).playerInfo.ally)
         {
            _loc4_ = lol.core.player.Trader(_loc2_);
            if(_loc4_.canRepair || _loc4_.canTrophy || _loc4_.canTrade)
            {
               this.trade = new lol.core.player.Trade();
               this.trade.ss_propose(obj.id);
            }
         }
         else if(_loc2_ instanceof lol.core.player.Auctioner && lol.core.player.NPC(_loc2_).playerInfo.ally)
         {
            _loc11_ = lol.core.player.Auctioner(_loc2_);
            this.auction = new lol.core.player.Auction();
            this.auction.ss_propose(obj.id);
         }
         else if(_loc2_ instanceof lol.core.player.Teacher && lol.core.player.NPC(_loc2_).playerInfo.ally)
         {
            this.training = new lol.core.player.Training();
            this.training.ss_propose(obj.id);
         }
         else if(_loc2_ instanceof lol.core.player.Upgrader && lol.core.player.NPC(_loc2_).playerInfo.ally)
         {
            this.upgrade = new lol.core.player.Upgrade();
            this.upgrade.ss_propose(obj.id);
         }
         else if(_loc2_ instanceof lol.core.player.Lessor && lol.core.player.NPC(_loc2_).playerInfo.ally)
         {
            this.rent = new lol.core.player.Rent();
            this.rent.ss_propose(obj.id);
         }
         else if(_loc2_ instanceof lol.core.player.Commoner && lol.core.player.NPC(_loc2_).playerInfo.ally)
         {
            _loc10_ = lol.core.player.Commoner(_loc2_);
            if(_loc10_.canBanking)
            {
               this.bank = new lol.core.player.Bank();
               this.bank.ss_propose(obj.id);
            }
            else
            {
               lol.core.player.NPCService.openService(_loc2_.id);
            }
         }
         else if(_loc2_ instanceof lol.core.player.Healer && lol.core.player.NPC(_loc2_).playerInfo.ally)
         {
            _loc9_ = lol.core.player.Healer(_loc2_);
            lol.core.player.NPCService.openService(_loc9_.id);
         }
      }
   }
   function ss_create(obj)
   {
      if(!this.barter)
      {
         this.barter = new lol.core.player.Barter();
         this.barter.ss_create(obj);
      }
   }
   function heal(obj)
   {
      var _loc5_ = lol.core.Master.getInstance();
      var _loc4_ = _loc5_.currentLocation;
      var _loc3_ = _loc4_.getCellFromNumber(this.walker.numPos);
      var _loc2_ = obj.targetCell;
      var _loc8_;
      var _loc6_;
      if(_loc3_ == _loc2_ || _loc4_.isSiblings(_loc3_,_loc2_))
      {
         this.walker.removeEventListener("finishMove",this);
         if(obj.id == lol.core.player.Gamer.ID)
         {
            this.useObjectIdle(this.equipment.primaryItem);
         }
         else
         {
            _loc8_ = 1;
            _loc6_ = lol.utils.MDString.createBigUINT([_loc8_,1],[obj.id,8]);
            this.useObjectToTarget(this.equipment.primaryItem,_loc6_);
            this.dispatchEvent(new lol.events.TimeBarEvent(lol.events.TimeBarEvent.HEAL,this.equipment.primaryItem));
         }
      }
   }
   function strike(obj)
   {
      var _loc5_ = lol.core.Master.getInstance();
      var _loc4_ = _loc5_.currentLocation;
      var _loc3_ = _loc4_.getCellFromNumber(this.walker.numPos);
      var _loc2_ = obj.targetCell;
      if(_loc3_ == _loc2_ || _loc4_.isSiblings(_loc3_,_loc2_))
      {
         this.walker.removeEventListener("finishMove",this);
         this.itemActivator.strike(1,obj.id);
      }
   }
   function strikeHex(pos)
   {
      this.itemActivator.strike(0,pos);
   }
   function clearTask()
   {
      this.walker.removeEventListener("finishMove",this);
      this.stuff_func = null;
      this.stuff_param = null;
   }
   function loadObject(fireArm, ammo)
   {
      this.itemActivator.loadObject(fireArm,ammo);
   }
   function useObjectIdle(item)
   {
      this.itemActivator.useObjectIdle(item);
   }
   function useObjectToTarget(item, target)
   {
      this.itemActivator.useObjectToTarget(item,target);
   }
   function useObjectToObject(item, target)
   {
      this.itemActivator.useObjectToObject(item,target);
   }
   function fire(targetType, target)
   {
      this.itemActivator.fire(targetType,target);
   }
   function unloadObject(fireArm)
   {
      this.itemActivator.unloadObject(fireArm);
   }
   function changeUseMode(fireArm, mode)
   {
      this.itemActivator.changeUseMode(fireArm,mode);
   }
   function deleteItem(item)
   {
      this.itemActivator.deleteObject(item);
   }
   function dispatchAck(res)
   {
      this.dispatchEvent({type:"useAck",res:res});
   }
   function kill()
   {
      this.XMC.removeEventListener("rp_info",this.attributes);
      this.XMC.removeEventListener("ss_obj_status",this.equipment);
      lol.server.XMLCCallStack.skipCall("userInfo",this,this.userInfo);
      this.XMC.removeEventListener("accountInfo",this);
      this.XMC.removeEventListener("ss_create",this);
      delete this.playerInfo;
      this.walker.removeEventListener("finishMove",this);
      this.walker.kill();
      this.loot.kill();
      this.barter.kill();
      this.equipment.kill();
      this.apManager.kill();
      this.ssMessages.kill();
      this.partyManager.kill();
      delete this.loot;
      delete this.barter;
      delete this.equipment;
      delete this.attributes;
      delete this.apManager;
      delete this.ssMessages;
      delete this.partyManager;
      delete this.walker;
      this.itemActivator.kill();
      this.itemActivator = null;
      this.acManager.kill();
      this.acManager = null;
   }
   function startPC()
   {
   }
   function addPC()
   {
      lol.utils.ProcessExplorer.callProcess("Gamer_" + this.id + "_" + this.spt,this.spt);
      clearInterval(this.spt_int);
      this.spt_int = setInterval(this,"addPC",300);
   }
}
