class lol.server.mess.CSM_SSGet extends lol.server.mess.CSMessage
{
   var _name;
   var addProp;
   function CSM_SSGet(slot, target)
   {
      super();
      this._name = "ss_get";
      this.addProp("target",target);
      this.addProp("slot",slot);
   }
}
