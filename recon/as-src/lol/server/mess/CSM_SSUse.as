class lol.server.mess.CSM_SSUse extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_SSUse(type, obj, target)
   {
      super();
      this._name = "ss_use";
      this.addProp("target",target);
      this.addProp("obj",obj);
      this.addProp("type",type);
   }
}
