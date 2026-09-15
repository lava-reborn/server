class lol.core.player.PersAttributes
{
   var XMC;
   var _afro;
   var _gold;
   var _health;
   var _maxHealth;
   var _maxStamina;
   var _max_specs;
   var _stamina;
   var ap_max;
   var armor;
   var attribArray;
   var dispatchEvent;
   var hp;
   var hp_max;
   var max_weight;
   var skill0;
   var skill1;
   var skill2;
   var skill3;
   var skill4;
   var skillArray;
   var sp;
   var sp_max;
   var spec0;
   var spec1;
   var spec2;
   var spec3;
   var spec4;
   var spec5;
   var spec6;
   var spec7;
   var spec8;
   var spec9;
   var spec10;
   var spec11;
   var spec12;
   var spec13;
   var spec14;
   var specArray;
   var specMatrix;
   static var INCREASE_SKILL = "INCREASE_SKILL";
   static var INCREASE_SPEC = "INCREASE_SPEC";
   static var INCREASE_LEVEL = "INCREASE_LEVEL";
   static var INCREASE_SPEC_LEVEL = "INCREASE_SPEC_LEVEL";
   var _level = 0;
   var skillNumber = 5;
   var specNumber = 15;
   var attribNumber = 5;
   var firstLoad = false;
   function PersAttributes()
   {
      lol.events.LEventDispatcher.initialize(this);
      this._health = 1200;
      this.maxHealth = 1200;
      this.XMC = lol.server.XMLConnection.getInstance();
      this.skillArray = new Array();
      this.specArray = new Array();
      this.attribArray = new Array();
      this.specMatrix = new Array();
      this.specMatrix = [0,0,1,1,1,1,1,1,2,2,3,3,4,4,4];
      var _loc2_ = 0;
      while(_loc2_ < this.attribNumber)
      {
         this["attrib" + _loc2_] = new lol.core.player.AttribObject();
         this["attrib" + _loc2_].id = _loc2_;
         this.attribArray[_loc2_] = this["attrib" + _loc2_];
         _loc2_ = _loc2_ + 1;
      }
      _loc2_ = 0;
      while(_loc2_ < this.skillNumber)
      {
         this["skill" + _loc2_] = new lol.core.player.SkillObject();
         this["skill" + _loc2_].id = _loc2_;
         this.skillArray[_loc2_] = this["skill" + _loc2_];
         this["skill" + _loc2_].addEventListener(lol.core.player.SkillObject.INCREASE_SKILL,this,this.increase_skill_func);
         this["skill" + _loc2_].addEventListener(lol.core.player.SkillObject.INCREASE_LEVEL,this,this.increase_level_func);
         _loc2_ = _loc2_ + 1;
      }
      this.skill0.title = "Ближнего боя";
      this.skill1.title = "Стрельбы";
      this.skill2.title = "Медицины";
      this.skill3.title = "Промышленность";
      this.skill4.title = "Производство";
      _loc2_ = 0;
      while(_loc2_ < this.specNumber)
      {
         this["spec" + _loc2_] = new lol.core.player.SpecObject();
         this["spec" + _loc2_].id = _loc2_;
         this.specArray[_loc2_] = this["spec" + _loc2_];
         this["spec" + _loc2_].addEventListener(lol.core.player.SpecObject.INCREASE_SPEC,this,this.increase_spec_func);
         this["spec" + _loc2_].addEventListener(lol.core.player.SpecObject.INCREASE_SPEC_LEVEL,this,this.increase_spec_level_func);
         _loc2_ = _loc2_ + 1;
      }
      this.spec0.title = "Рукопашный бой";
      this.spec1.title = "Режущее оружие";
      this.spec2.title = "Пистолеты";
      this.spec3.title = "Дробовики";
      this.spec4.title = "Автоматы";
      this.spec5.title = "Винтовки";
      this.spec6.title = "Ручные пулеметы";
      this.spec7.title = "Пистолет-пулеметы";
      this.spec8.title = "Хирургия";
      this.spec9.title = "Первая помощь";
      this.spec10.title = "Добыча";
      this.spec11.title = "Переработка";
      this.spec12.title = "Мастер свинца";
      this.spec13.title = "Мастер селитры";
      this.spec14.title = "Мастер меди";
      this.spec0.min_skill_level = 0;
      this.spec1.min_skill_level = 0;
      this.spec2.min_skill_level = 0;
      this.spec3.min_skill_level = 4;
      this.spec4.min_skill_level = 12;
      this.spec5.min_skill_level = 6;
      this.spec6.min_skill_level = 16;
      this.spec7.min_skill_level = 8;
      this.spec8.min_skill_level = 0;
      this.spec9.min_skill_level = 0;
      this.spec10.min_skill_level = 0;
      this.spec11.min_skill_level = 0;
      this.spec12.min_skill_level = 0;
      this.spec13.min_skill_level = 0;
      this.spec14.min_skill_level = 0;
      this.specInSkill();
   }
   function requestAttributes()
   {
      var _loc2_;
      if(!this.firstLoad)
      {
         _loc2_ = new lol.server.mess.CSM_RPGetInfo();
         this.XMC.Send(_loc2_);
         this.firstLoad = true;
      }
   }
   function rp_info(obj)
   {
      var _loc4_;
      var _loc3_;
      this.updateParam(obj.param.a_attribs_mask,obj.param.a_attribs,"value","attrib");
      this.updateParam(obj.param.f_attribs_mask,obj.param.f_attribs,"value_bonus","attrib");
      this.updateParam(obj.param.a_skills_mask,obj.param.a_skills,"value","skill");
      this.updateParam(obj.param.f_skills_mask,obj.param.f_skills,"value_bonus","skill");
      this.updateParam(obj.param.xp_skills_mask,obj.param.xp_skills,"xp_skills","skill");
      this.updateParam(obj.param.xp_max_skills_mask,obj.param.xp_max_skills,"xp_max_skills","skill");
      this.updateParam(obj.param.a_specs_mask,obj.param.a_specs,"value","spec");
      this.updateParam(obj.param.f_specs_mask,obj.param.f_specs,"value_bonus","spec");
      this.updateParam(obj.param.xp_specs_mask,obj.param.xp_specs,"xp_specs","spec");
      this.updateParam(obj.param.xp_max_specs_mask,obj.param.xp_max_specs,"xp_max_specs","spec");
      if(obj.param.max_specs)
      {
         this.max_specs = obj.param.max_specs;
      }
      if(obj.param.hp)
      {
         this.hp = obj.param.hp;
         lol.core.Master.getInstance().gamer.health = this.hp;
      }
      if(obj.param.hp_max)
      {
         this.hp_max = obj.param.hp_max;
         lol.core.Master.getInstance().gamer.maxHealth = this.hp_max;
      }
      if(obj.param.sp)
      {
         this.sp = obj.param.sp;
         lol.core.Master.getInstance().gamer.stamina = this.sp;
      }
      if(obj.param.sp_max)
      {
         this.sp_max = obj.param.sp_max;
         lol.core.Master.getInstance().gamer.maxStamina = this.sp_max;
      }
      if(obj.param.ap_max)
      {
         this.ap_max = obj.param.ap_max;
      }
      if(obj.param.max_weight)
      {
         this.max_weight = obj.param.max_weight;
      }
      this.armor = obj.param.armor;
      if(obj.param.lvl)
      {
         this._level = obj.param.lvl;
      }
      this.dispatchEvent(new lol.events.PlayerEvent(lol.events.PlayerEvent.UPDATE_PARAMS));
   }
   function updateParam(m, dataArray, param, str)
   {
      var _loc5_ = m;
      var _loc4_ = 0;
      var _loc6_ = this[str + "Number"];
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < _loc6_)
      {
         _loc3_ = _loc5_ >> _loc2_ & 1;
         if(_loc3_)
         {
            this[str + _loc2_][param] = dataArray[_loc4_];
            _loc4_ = _loc4_ + 1;
         }
         _loc2_ = _loc2_ + 1;
      }
   }
   function specInSkill()
   {
      var _loc2_ = 0;
      var _loc3_;
      while(_loc2_ < this.specNumber)
      {
         _loc3_ = this.specMatrix[_loc2_];
         this.skillArray[_loc3_].specArr.push(this["spec" + _loc2_]);
         _loc2_ = _loc2_ + 1;
      }
   }
   function getSpecNumber()
   {
      var _loc2_ = 0;
      for(var _loc3_ in this.specArray)
      {
         if(this.specArray[_loc3_].available)
         {
            _loc2_ = _loc2_ + 1;
         }
      }
      return _loc2_;
   }
   function getLevel()
   {
      var _loc2_ = 0;
      for(var _loc3_ in this.skillArray)
      {
         if(this.skillArray[_loc3_].level != undefined && _loc2_ < this.skillArray[_loc3_].level)
         {
            _loc2_ = this.skillArray[_loc3_].level;
         }
      }
      return _loc2_;
   }
   function get health()
   {
      return this._health;
   }
   function set health(h)
   {
      this._health = h;
      if(this._health < 0)
      {
         this._health = 0;
      }
      if(this._health > this.maxHealth)
      {
         this._health = this.maxHealth;
      }
   }
   function get maxHealth()
   {
      return this._maxHealth;
   }
   function set maxHealth(h)
   {
      this._maxHealth = h;
   }
   function get stamina()
   {
      return this._stamina;
   }
   function set stamina(s)
   {
      this._stamina = s;
      if(this._stamina < 0)
      {
         this._stamina = 0;
      }
      if(this._stamina > this.maxStamina)
      {
         this._stamina = this.maxStamina;
      }
   }
   function get maxStamina()
   {
      return this._maxStamina;
   }
   function set maxStamina(s)
   {
      this._maxStamina = s;
   }
   function get max_specs()
   {
      return this._max_specs;
   }
   function set max_specs(s)
   {
      this._max_specs = s;
   }
   function get afro()
   {
      return this._afro;
   }
   function set afro(a)
   {
      this._afro = a;
      if(this._afro < 0)
      {
         this._afro = 0;
      }
   }
   function get gold()
   {
      return this._gold;
   }
   function set gold(g)
   {
      this._gold = g;
      if(this._gold < 0)
      {
         this._gold = 0;
      }
   }
   function get level()
   {
      return this._level;
   }
   function set level(lvl)
   {
      if(lvl != undefined)
      {
         this._level = lvl;
      }
   }
   static function compareLevels(lvlA, lvlB)
   {
      var _loc1_ = lvlA - lvlB;
      var _loc2_;
      if(_loc1_ <= -4)
      {
         _loc2_ = -4;
      }
      else if(_loc1_ == -3)
      {
         _loc2_ = -3;
      }
      else if(_loc1_ == -2)
      {
         _loc2_ = -2;
      }
      else if(_loc1_ == -1)
      {
         _loc2_ = -1;
      }
      else if(_loc1_ == 0)
      {
         _loc2_ = 0;
      }
      else if(_loc1_ == 1)
      {
         _loc2_ = 1;
      }
      else if(_loc1_ == 2)
      {
         _loc2_ = 2;
      }
      else if(_loc1_ == 3)
      {
         _loc2_ = 3;
      }
      else if(_loc1_ >= 4)
      {
         _loc2_ = 4;
      }
      return _loc2_;
   }
   function increase_skill_func(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_ = _loc2_.id;
      var _loc3_ = obj.value;
      this.dispatchEvent({type:lol.core.player.SkillObject.INCREASE_SKILL,id:_loc4_,value:_loc3_});
   }
   function increase_spec_func(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_ = _loc2_.id;
      var _loc3_ = obj.value;
      this.dispatchEvent({type:lol.core.player.SpecObject.INCREASE_SPEC,id:_loc4_,value:_loc3_});
   }
   function increase_level_func(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_ = _loc2_.id;
      var _loc3_ = obj.value;
      this.dispatchEvent({type:lol.core.player.SkillObject.INCREASE_LEVEL,id:_loc4_,value:_loc3_});
   }
   function increase_spec_level_func(obj)
   {
      var _loc2_ = obj.target;
      var _loc4_ = _loc2_.id;
      var _loc3_ = obj.value;
      this.dispatchEvent({type:lol.core.player.SpecObject.INCREASE_SPEC_LEVEL,id:_loc4_,value:_loc3_});
   }
}
